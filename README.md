# iPod Data Recovery — README

**Date:** 7 October 2026  
**Device:** 160GB Apple iPod (HFS+ / "Mac-formatted"), connected via USB to my Fedora laptop Macbook Air 2013 (`maccie')  
**Symptom:** iPod visible to the OS (Windows and Fedora), but the volume would not mount; The iPod reported "0KB used/free" despite \~40GB of music on it
**Outcome:** ✅ Full recovery — 6,959 files (\~51GB) carved with PhotoRec, sorted into `Artist/Album/Track - Title` from embedded tags

---

## Background

The iPod contained \~40GB of music accumulated over years, digitised from my old CD collection; the only copy as I have lost the backup drives and CDs. At some point an iTunes "erase and sync" was interrupted, leaving the filesystem's index structures damaged. The drive itself was healthy throughout: **every diagnostic showed clean reads with zero I/O errors.** The damage was to the filesystem "map," not the data.

---

## The Journey: Failures and Successes

### 1. Mount attempt — ❌ Failed

```bash
sudo mount -t hfsplus -o ro /dev/sdc /mnt/ipod
```

Error: `wrong fs type, bad option, bad superblock`. dmesg showed:

```
hfsplus: invalid secondary volume header
hfsplus: unable to find HFS+ superblock
```

**Lesson:** the kernel reads both the primary volume header (start of disk) *and* the backup (end of disk); a broken backup alone can block mounting.

### 2. Journal-skip mount attempt — ❌ Failed

`-o noload` was rejected: Fedora's kernel doesn't support the `noload` parameter for hfsplus. Some kernels use `ro,journal=off` or `ro,nojournal` instead.

### 3. fsck.hfsplus (read-only check) — ❌ Failed

```
sudo fsck.hfsplus -fn /dev/sdc
** The volume   could not be verified completely.
```

Blank volume name = badly damaged header. (Fedora note: the package is `hfsplus-tools`, not `hfsprogs`.)

### 4. ddrescue whole-disk image — ⏭️ Skipped

The textbook-safe route, but the laptop had only \~111GB free and no external drive had 160GB. Recovery proceeded without a safety image (calculated risk), mitigated by the fact that the drive showed no I/O errors.

**Lesson:** if you can make an image first, make the image first.

### 5. fsck.hfsplus (repair attempt) — ❌ Segfault

The Linux port of `fsck.hfsplus` crashed on the damaged volume. A tool crash, not a verdict on the data.

### 6. TestDisk diagnosis — ✅ Key breakthrough

```bash
sudo testdisk /dev/sdc
```

TestDisk found:

- **Primary volume header: OK** (signature `H+` / `HFSJ` confirmed via `od -A x -t x1z`)
- **Backup volume header: Bad**

So the primary was healthy. The mount failure was largely the invalid backup header. TestDisk 7.2 had no automated "Repair BS" option for HFS+ in this build, so the repair was done manually.

### 7. Manual header repair with dd — ✅ Partial success

Copied the good 512-byte primary volume header over the broken backup location (1024 bytes before end of disk):

```bash
SIZE=$(sudo blockdev --getsize64 /dev/sdc)        # 159840301056
BACKUP_OFF=$((SIZE - 1024))                       # 159840300032

# save the broken backup first (undo file!)
sudo dd if=/dev/sdc of=~/vh-bad-backup.bin bs=1 skip=$BACKUP_OFF count=512
# read the good primary (1024 bytes into the disk)
sudo dd if=/dev/sdc of=~/vh-primary.bin bs=512 skip=2 count=1

# verify before writing: they must differ
sudo cmp ~/vh-primary.bin ~/vh-bad-backup.bin      # differ: byte 1 ✓

# the repair
sudo dd if=~/vh-primary.bin of=/dev/sdc bs=1 seek=$BACKUP_OFF count=512 conv=notrunc
sync
```

Result: the kernel got further; it now found the header, replayed the journal state, but then:

```
hfsplus: Filesystem was not cleanly unmounted... mounting read-only.
hfsplus: invalid extent max_key_len 65535
hfsplus: failed to load extents file
```

**Lesson:** dmesg changing between attempts is progress, even when the mount still fails — each error names the next damaged structure.

### 8. Extents-file repair — ❌ Dead end on Linux

The extents B-tree was also damaged (another casualty of the interrupted sync). Rebuilding a B-tree by hand isn't feasible, and the only Linux tool (`fsck.hfsplus`) segfaults. A Mac with native Disk Utility would likely repair this cleanly. Worth trying if one is available.

### 9. PhotoRec carve — ✅ The recovery

With the filesystem unrepairable on Linux, switched to carving files straight out of the raw disk:

```bash
sudo photorec /dev/sdc
```

- Filesystem type: **Other** (FAT/NTFS/HFS+/...)
- Scan: **Whole disk**
- File types: **mp3 and m4a only** (via File Opt — essential to avoid thousands of junk blobs)
- Destination: external SD Card (used for my camera) (exFAT, mounted at `/run/media/sidd/EOS_DIGITAL`)

\~1.5 hours later: **6,959 files, \~51GB** in `recup_dir.*` folders. Filenames are arbitrary (`f0059396.mp3`) and some files are mislabelled `.txt` (headerless MPEG audio — detectable via magic bytes `ff fb` / `ff f3` / `ff f2`).

**Lesson:** the tags (artist/album/track/title) live *inside* the audio files as metadata tags, so losing filenames and folder structure costs almost nothing.

### 10. Tag-based rebuild — ✅ Sorted library

A Python script (`mutagen` — package `python3-mutagen` on Fedora) walked the recup\_dir folders, read each file's tags, and rebuilt:

```
recovered-music/
└── Artist/
    └── Album/
        └── 01 - Track Title.m4a
```

Key details of the script:

- `mutagen.File(path, easy=True)` handles mp3 and m4a uniformly; no need for separate EasyID3/MP4 imports
- Extension filter first, then `.txt`-magic check to catch headerless MPEG audio
- Filenames sanitised (`/ \ : * ? " < > |` → `_`)
- Files **copied**, not moved, so the raw photorec output stayed intact as the second copy

---

## Timeline Summary


| Step | Tool               | Result                                              |
| ---- | ------------------ | --------------------------------------------------- |
| 1    | `mount`            | ❌ invalid backup volume header                     |
| 2    | `mount -o noload`  | ❌ kernel doesn't support option                    |
| 3    | `fsck.hfsplus -fn` | ❌ could not verify                                 |
| 4    | `ddrescue` image   | ⏭️ skipped (no 160GB free anywhere)                 |
| 5    | `fsck.hfsplus -f`  | ❌ segfault (tool bug)                              |
| 6    | `testdisk`         | ✅ diagnosed: primary OK, backup bad                |
| 7    | `dd` header copy   | ✅ backup header repaired; extents file exposed     |
| 8    | extents repair     | ❌ dead end on Linux (Mac Disk Utility could do it) |
| 9    | `photorec`         | ✅ 6,959 files / \~51GB carved                      |
| 10   | `mutagen` script   | ✅ sorted library from tags                         |


---

## Lessons Learned

1. **Zero I/O errors in dmesg = the data is probably fine; it's the index that's broken.** That distinction drives every decision.
2. **No I/O errors ≠ no risk.** Repairs without an image are one-shot; the 160GB image couldn't be made here, so each write was verified (`cmp`, `od` magic bytes, undo file saved) before committing.
3. **Save the bytes you're about to overwrite** (`vh-bad-backup.bin`) — repairs become reversible.
4. **Change one error message at a time.** Each mount attempt peeled one layer: backup header → journal → extents file.
5. **When the filesystem is unrepairable, don't repair — carve.** PhotoRec ignores the filesystem entirely, and embedded tags restore the structure.
6. **Filter PhotoRec to mp3/m4a only**, or spend a day sorting junk out of the output.
7. **Backups are cheaper than recovery.** \~10 hours of careful work went into 40GB that a £20 drive would have protected.
8. **3-2-1 rule**. Three copies of the data, using two different types of storage media, and one copy stored off-site. 

---

## Post-Recovery Checklist

- [x] Raw photorec output kept on external stick (first copy)
- [x] Sorted library on laptop (second copy)
- [x] Sample-listen to random albums; check for truncations
- [x] Review script's "untagged" list (fragments without tags)
- [ ] Eventually make a third, proper backup copy
- [ ] iPod itself: keep as beloved paperweight with a good story
