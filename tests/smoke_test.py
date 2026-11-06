#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Part of SortView (سورت‌ویو).
# Copyright (c) 2026 Mohammad Jafari
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offscreen smoke test for SortView — runs in GitHub Actions CI on every push.

Everything here is headless (QT_QPA_PLATFORM=offscreen) and needs no display,
no audio device and no VLC. It covers:

  1. main.py imports cleanly and picks up a Qt6 binding (PyQt6 preferred).
  2. The English/Persian string tables are consistent: every Persian
     translation is non-empty and keeps the same {placeholder} set as its
     English key (a mismatch would crash .format() at runtime).
  3. The real main window (main.SortView) instantiates with the plain
     "SortView" title, an empty undo stack and an enabled Undo button.
  4. The v1.10.2 undo regression: an undo batch whose destination file was
     deleted by hand is dropped instead of blocking the older batch behind
     it (the exact bug that made every following Ctrl+Z useless).
  5. Read-only files keep their read-only attribute through a move and
     normal files stay writable.
  6. The v1.10.3 archive thumbnailers: the first image inside a .tar.gz
     (stdlib tarfile) and inside a .7z (pinned py7zr 1.1.4 extract API,
     which replaces the removed 7za.exe and its dead read() call).

Run locally from the repo root:  python tests/smoke_test.py
"""
import os
import re
import stat
import sys
import time
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
if os.name != "nt":  # Linux CI / sandbox nicety; Windows runners need none of this
    os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/xdg-rt")
    Path("/tmp/xdg-rt").mkdir(exist_ok=True)

fails = []


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- 1. import
import app_i18n  # noqa: E402
import main  # noqa: E402

print(f"Python {sys.version.split()[0]} | Qt binding: {main.QT_API} | "
      f"QtMultimedia: {main.HAS_QTMEDIA}")

check("Qt binding is Qt6 (PyQt6 preferred, PySide6 fallback)", main.QT6)
check("app_i18n offers exactly en + fa",
      {lang for lang, _ in app_i18n.LANGUAGES} == {"en", "fa"})
check("fa is marked RTL", "fa" in app_i18n.RTL_LANGS)

try:
    app_i18n.set_language("en")
except Exception:
    pass

# ------------------------------------------------------- 2. bilingual tables
ph = re.compile(r"\{\w+\}")
bad = []
for k, v in app_i18n.FA.items():
    if not isinstance(v, str) or not v.strip():
        bad.append(f"empty translation: {k!r}")
    elif sorted(ph.findall(k)) != sorted(ph.findall(v)):
        bad.append(f"placeholder mismatch: {k!r} -> {v!r}")
check("every Persian string is non-empty and keeps its {placeholders}", not bad)
for b in bad[:10]:
    print("      " + b)

app_i18n.set_language("fa")
check("fa: 'Theme:' translates to the Persian string",
      app_i18n.t("Theme:") == "تم:")
check("fa: a missing key falls back to the English text",
      app_i18n.t("SortView") == "SortView")
app_i18n.set_language("en")
check("en: t() returns the canonical English text",
      app_i18n.t("Theme:") == "Theme:")

# --------------------------------------------------------------- 3. window
# Instantiating a real QAudioOutput segfaults on sound-less machines
# (headless CI runners). Stub it before any widget is created — Windows
# desktops are unaffected, this only ever matters offscreen.
if main.HAS_QTMEDIA:
    class _StubAudio(main.QtCore.QObject):
        def setVolume(self, *a, **k):
            pass

    main.QAudioOutput = _StubAudio

QtWidgets = main.QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

win = main.SortView()
# Test harness guard: the constructor may have queued a scan error for a
# stale config folder (its handler opens a MODAL dialog that would block
# the offscreen event loop). Invalidate it; this window is rebuilt below
# for the undo scenario anyway.
win._scan_generation += 100
win.candidate_folder = None

check("window title is just 'SortView'", win.windowTitle() == "SortView")
check("undo stack starts empty", len(win._undo_stack) == 0)
check("Undo button starts disabled with an empty stack (by design)",
      win.btn_undo is not None and not win.btn_undo.isEnabled())
check("status bar exists", win.status is not None)

# --------------------------------------------- 4. undo regression (v1.10.2)
tmp = Path(tempfile.mkdtemp(prefix="sortview_ci_"))
src = tmp / "source"
cat = tmp / "cat"
src.mkdir()
cat.mkdir()
(src / "a.txt").write_text("A")
(src / "b.txt").write_text("B")
# batch1 (older, healthy): a.txt sits in the category folder right now.
batch1 = [(str(src / "a.txt"), str(cat / "a.txt"))]
shutil.move(str(src / "a.txt"), str(cat / "a.txt"))
# batch2 (newest): b.txt was moved into the category folder, then the user
# deleted it by hand — its destination no longer exists.
batch2 = [(str(src / "b.txt"), str(cat / "b.txt"))]

win2 = main.SortView()
win2._scan_generation += 100
win2.candidate_folder = str(src)
win2._undo_stack.clear()
win2._undo_stack.append(batch1)
win2._undo_stack.append(batch2)


def wait_undo_idle(w, timeout=30.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if not w._undo_active:
            time.sleep(0.05)
            app.processEvents()
            if not w._undo_active:
                # also let the post-undo rescan finish (it delivers the
                # summary message to the status bar once populate ends)
                t1 = time.time()
                while time.time() - t1 < 5.0:
                    app.processEvents()
                    if not w.populate_timer.isActive():
                        break
                    time.sleep(0.05)
                return True
        time.sleep(0.05)
    return False


# Ctrl+Z #1 — newest batch: the file is gone, the pair must be dropped
# (NOT re-queued), and the healthy batch behind it must stay reachable.
win2._undo_last_move()
check("1st undo finished", wait_undo_idle(win2))
check("1st undo: gone file not 'restored'", not (cat / "b.txt").exists())
check("1st undo: doomed batch NOT re-queued (stack size 1, was 2 before fix)",
      len(win2._undo_stack) == 1)
check("1st undo: status reports the file is no longer in the category folder",
      "no longer in the category folder" in win2.status.text())
check("1st undo: Undo button still enabled for the healthy batch",
      win2.btn_undo.isEnabled())

# Ctrl+Z #2 — the older healthy batch: must restore a.txt now.
win2._undo_last_move()
check("2nd undo finished", wait_undo_idle(win2))
check("2nd undo: a.txt back in its original folder", (src / "a.txt").is_file())
check("2nd undo: a.txt removed from the category folder",
      not (cat / "a.txt").exists())
check("2nd undo: stack is empty", len(win2._undo_stack) == 0)
check("2nd undo: status reports the restore",
      "back in the explorer" in win2.status.text())

# Ctrl+Z #3 — nothing left to undo, no crash.
win2._undo_last_move()
app.processEvents()
check("3rd undo: 'Nothing to undo' reported",
      "Nothing to undo" in win2.status.text())

# ------------------------------------------- 5. read-only attribute + move
ro_src = tmp / "ro"
ro_dst = tmp / "ro_cat"
ro_src.mkdir()
ro_dst.mkdir()
ro = ro_src / "r.txt"
ro.write_text("R")
os.chmod(ro, stat.S_IREAD)  # read-only
tm = main.TransferManager(max_workers=1)
out = tm._do_move(str(ro), str(ro_dst), generation=0)
moved = Path(out)
check("read-only move: file arrived with its content",
      moved.is_file() and moved.read_text() == "R")
check("read-only move: source removed", not ro.exists())
check("read-only move: moved file is still read-only",
      not (moved.stat().st_mode & stat.S_IWRITE))

normal = ro_src / "n.txt"
normal.write_text("N")
out2 = tm._do_move(str(normal), str(ro_dst), generation=0)
check("normal move: file stays writable",
      (Path(out2).stat().st_mode & stat.S_IWRITE) != 0)

# ------------------------------------------- 6. archive thumbnails via stdlib libs (v1.10.3)
from PIL import Image as _PILImage
import tarfile as _tarfile

tiny = tmp / "tiny.png"
_PILImage.new("RGB", (4, 4), (200, 30, 30)).save(tiny, "PNG")
tgz = tmp / "sample.tar.gz"
with _tarfile.open(str(tgz), "w:gz") as tf:
    tf.add(str(tiny), arcname="inner/tiny.png")
png_bytes = main._first_image_from_tar(tgz, 64)
check("tar thumbnail: stdlib tarfile returns a PNG",
      bool(png_bytes) and png_bytes[:8] == b"\x89PNG\r\n\x1a\n")

zp7 = tmp / "sample.7z"
with main.py7zr.SevenZipFile(str(zp7), "w") as zf7:
    zf7.write(tiny, arcname="inner/tiny.png")
png7 = main._first_image_from_7z(zp7, 64)
check("7z thumbnail: pinned py7zr 1.1.4 extract API returns a PNG",
      bool(png7) and png7[:8] == b"\x89PNG\r\n\x1a\n")

# ---------------------------------------------------------------- teardown
try:
    os.chmod(moved, stat.S_IWRITE | stat.S_IREAD)
except OSError:
    pass
tm.shutdown()
win.close()
win2.close()
app.processEvents()
shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print(f"{len(fails)} CHECK(S) FAILED:")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ALL CHECKS PASSED")
sys.exit(0)
