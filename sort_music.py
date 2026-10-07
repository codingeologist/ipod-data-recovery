#!/usr/bin/env python3
import os, shutil, sys
from mutagen import File


SRC = "/run/media/sidd/EOS_DIGITAL/ipod_backup"
DST = os.path.expanduser("~/recovered-music")

def clean(s):
    return "".join(c if c not in '/\\:*?"<>|' else "_" for c in s).strip() or "Unknown"

untagged = []
count = 0
for root, _, files in os.walk(SRC):
    for name in files:
        path = os.path.join(root, name)

        ext = os.path.splitext(name)[1].lower()
        if ext not in (".mp3", ".m4a", ".m4b", ".aa", ".txt"):
            continue
        if ext == ".txt":
            # only keep .txt files that look like audio
            with open(path, "rb") as f:
                magic = f.read(2)
            if magic not in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
                continue  # genuine junk — skip
            ext = ".mp3"  # headerless MPEG audio

        try:
            audio = File(path, easy=True)
        except Exception:
            audio = None
        if audio is None or not audio.tags:
            untagged.append(path)
            continue
        artist = clean(str(audio.get("artist", ["Unknown Artist"])[0]))
        album  = clean(str(audio.get("album", ["Unknown Album"])[0]))
        title  = clean(str(audio.get("title", [os.path.splitext(name)[0]])[0]))
        track  = str(audio.get("tracknumber", [""])[0]).split("/")[0]
        ext    = os.path.splitext(name)[1].lower()
        prefix = f"{int(track):02d} - " if track.isdigit() else ""
        outdir = os.path.join(DST, artist, album)
        os.makedirs(outdir, exist_ok=True)
        shutil.copy2(path, os.path.join(outdir, f"{prefix}{title}{ext}"))
        count += 1

print(f"Sorted {count} files into {DST}")
if untagged:
    print(f"{len(untagged)} files had no tags:")
    for p in untagged[:20]:
        print("  ", p)
