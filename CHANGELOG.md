# Changelog

All notable changes to **SortView (سورت‌ویو)** are documented here.

## [1.10.3] — Much smaller portable build

The portable package used to carry four native tools "just in case". An
audit of what the app actually calls showed that only one of them is ever
used, so the build now bundles just that one and the release zip shrinks
by roughly 140 MB.

- **VLC runtime removed (−77 MB inside the zip).** Videos and audio play
  through Qt Multimedia, whose FFmpeg backend ships inside the PyQt6 wheel
  itself (verified: `libffmpegmediaplugin` plus `libavcodec`/`libavformat`/
  `libswscale` are in every PyQt6 >= 6.9 wheel). libVLC was only the second
  fallback and was never reached on a healthy install. The `python-vlc`
  pip dependency is dropped with it; the dormant libVLC/ffplay code paths
  remain in the source for dev machines and cost nothing at runtime.
- **`ffplay.exe` removed (−31 MB).** It only ran when BOTH Qt Multimedia
  and libVLC had already failed — effectively never. `_launch_external_player`
  already returns cleanly when the tool is absent.
- **`ffprobe.exe` removed (−31 MB).** Its only wrapper, `ffprobe_duration()`,
  had zero callers — dead code found by this audit. Video thumbnails keep
  their single fast `ffmpeg` call (unchanged).
- **`7za.exe` removed (−1 MB, one less unsigned exe for antivirus to
  flag).** Archive thumbnails were ALREADY done by pip libraries: `py7zr`
  for `.7z`, stdlib `zipfile` for `.zip`, `rarfile` for `.rar`. A new
  stdlib `tarfile` thumbnailer now covers `.tar`/`.tar.gz` (the one job
  7za still did); a system 7-Zip found on PATH is still used opportunistically.
- **Fixed: `.7z` archive thumbnails were silently broken.** The thumbnailer
  still called `archive.read()` — a py7zr 0.x API that no longer exists in
  the pinned py7zr 1.1.4 (`'SevenZipFile' object has no attribute 'read'`),
  so every `.7z` fell through to a type card. It now uses the 1.x
  `extract(targets=...)` API into a temp dir with a path-containment check,
  and the smoke test covers both `.7z` and `.tar.gz` (checks #27/#28).
- **Build-time downloads shrink from ~164 MB to ~88 MB** (only the pinned
  ffmpeg 7.1.1 essentials build remains, hash-verified as before, GPL
  license text still shipped next to it).
- Docs updated everywhere (README EN/FA, THIRD_PARTY_NOTICES, SECURITY);
  the "no video player" status messages no longer tell users to install
  VLC.
- New smoke-test checks #27/#28: the tarfile thumbnailer extracts the first
  image from a `.tar.gz`, and the py7zr 1.1.4 extract API from a `.7z`
  (28 named checks now, up from 26).
- **Docs precision:** the Safety notice now states exactly what is
  verified after a cross-drive copy (a size check — the copy is fsynced
  and size-compared before the source is deleted; no hash pass), and
  both READMEs explain that the demo GIFs' color banding and slight
  color shifts come from GIF compression (256 colors per frame), not
  from the app.


## [1.10.2] — Undo & safety fixes

Bug-fix release: one real logic bug, five safety/robustness hardenings,
a fresh-clone build fix, small documentation corrections. No new
features.

### Fixed
- **Undo no longer gets stuck when a moved file has vanished.** If a file
  that had been moved into a category folder was then moved away or
  deleted by hand, every following `Ctrl+Z` re-tried the same doomed
  batch: the failed pairs were pushed back onto the undo stack as a
  block, the Undo button stayed enabled but nothing was ever restored,
  and older transfer rounds behind it never became reachable again. The
  undo worker now reports "the file is no longer in the category folder"
  separately; such pairs are dropped (there is nothing to restore) and
  only pairs that failed for a real reason (e.g. a file locked by another
  program) are re-queued for the next `Ctrl+Z`.
- **Undo of read-only files works across drives too.** Moving such a file
  back with copy+delete hit the read-only source delete and reported a
  failure every time. The undo worker now falls back to an explicit copy
  plus a read-only-aware delete of the source.
- **Read-only files stay read-only after a same-drive move.** The
  hardlink path deletes the source through `force_unlink()`, which clears
  the Windows read-only attribute — an attribute both hardlinks share, so
  the moved copy silently lost it. The attribute is now restored on the
  destination after the move.
- **"Run this file?" now defaults to No.** The confirmation before
  opening a program-like file offered Yes/No with Enter falling on
  **Yes**; the safe answer is the default now. The guarded extension list
  also grew: `.url`, `.reg`, `.pif`, `.vbe`, `.wsh`, `.chm`, `.cpl`,
  `.msc`, `.docm`, `.xlsm`, `.py` and `.pyw` now ask before opening,
  just like `.exe`/`.bat` already did.
- **Archive thumbnails: entry names are no longer treated as wildcards.**
  7-Zip interprets `*` and `?` in an entry name passed on its command
  line, so an archive whose first image is named e.g. `photo?.png` could
  never show it. The `-spd` switch disables that interpretation for both
  the listing and the extraction calls.
- **Cross-drive moves verify the copy before deleting the source.** When
  a move cannot use a hardlink (USB stick, another drive), the file is
  copied chunk by chunk and the source is removed afterwards. The
  destination size is now compared with the source size before that
  removal; on a mismatch the partial copy is deleted, the source stays
  untouched and the transfer fails with a clear error instead of
  silently losing data.
- **`build_deps.ps1` works on a fresh clone again.** The script copied
  ffmpeg/ffprobe/ffplay into the gitignored `bin\` folder before
  creating it, so on a clean checkout — where `bin\` does not exist —
  staging aborted with "Runtime dependency staging failed" and
  `BUILD.bat` stopped. `bin\` is now created up front, next to the
  staging and download folders.

### Changed
- **The window title is just "SortView" now.** The Qt binding name
  (PyQt6/PySide6) that used to trail the title was implementation
  detail, not product information. The binding actually loaded is
  written to `app.log` at startup instead, so support reports can still
  show it.
- **The README pictures are real captures of the app now.** The
  screenshots and demo GIFs in both READMEs were re-recorded from the
  running program (window-region captures, GIFs compressed to 1–2 MB
  each). Each language now carries three demo GIFs — moving files with
  the number keys, managing categories (create, rename, delete), and
  resizing the three-panel layout — and every picture sits in the
  section that describes it. Both READMEs note that the captures are
  real while the sample files shown inside them (pictures, chart,
  document, audio and video clips, archives, text/code files) were
  generated with AI; the disclosure for the app and README text
  itself stays.
- **Both READMEs document the Undo limits:** the undo history lives in
  memory only (up to 50 transfer rounds) and is cleared when SortView
  closes.
- **Both READMEs carry a Safety notice.** SortView moves real files and
  its transfer logic is built to never overwrite and to delete a source
  only after a verified copy, but the risk of data loss is small — not
  zero (antivirus locks, failing drives, a power cut mid-transfer).
  Readers are told not to use SortView on important files — or to keep
  a backup of them first, so nothing is truly lost if a file is
  deleted — to practice on a folder copy, and that the app comes
  without any warranty under GPL-3.0.
- **Both READMEs open with a table of contents.** Every section is one
  click away from the top, English and Persian alike; the Persian
  anchor links follow GitHub's own heading-slug rules.
- **GitHub Actions CI now tests every push.** The new workflow
  (`.github/workflows/ci.yml`) installs the locked dependencies on a
  Windows runner, byte-compiles all sources and runs
  `tests/smoke_test.py` — an offscreen Qt smoke test (no display, no
  audio device, no VLC) that imports the app, checks the
  English/Persian string tables, launches the real main window and
  replays the v1.10.2 undo regression plus the read-only move checks.
  Every commit shows a green/red check in the Actions tab.
- **`.gitignore` no longer ignores `tests/`.** The ignore entry predated
  CI and silently kept the new smoke-test folder out of the first CI
  commit, so that first Actions run failed on GitHub. The folder is
  tracked now and the next run goes green.
- The FAQ answers the internet question more precisely: the app itself
  makes no network connections (QtNetwork is only loaded internally as a
  dependency of the bundled media engine).

## [1.10.1] — Documentation

Documentation-only release; the application itself is identical to 1.10.0.

### Changed
- **Both READMEs (EN + FA) state that the sample pictures in the
  screenshots and demo GIFs are AI-generated placeholders.**
- **Persian README changelog pointer** updated (it still showed 1.9.2).

## [1.10.0] — Security, build & cleanup round

One security-critical dependency bump, three reproducibility/licence
fixes in the build chain, two file-handling bug fixes and one repo
cleanup. No UI changes.

### Security
- **Pillow 11.3 → 13.0.0 in `requirements-lock.txt`** (and
  `Pillow>=13.0` in `requirements.txt`). `pip-audit` reports ~37 known
  vulnerabilities for the 11.x line, including heap overflows when
  decoding crafted JPEG/TIFF/JPEG2000 files — relevant because SortView
  opens unknown user files to build thumbnails. Verified end to end with
  13.0.0: png/jpg/gif/webp/tiff/bmp/zip/pdf thumbnails and the whole
  test suite pass unchanged.

### Fixed
- **Video thumbnails no longer leak PNGs into the system TEMP folder.**
  `extract_frame_with_ffmpeg()` writes one file per seek attempt
  (`..._a0.png`, `..._a1.png`, ...) and returned the successful one —
  which `generate_thumbnail_bytes()` then never deleted, so every video
  thumbnail left 1–2 PNGs in `%TEMP%` forever (measured before the fix:
  5 videos → 5 leftovers). The extraction helper now deletes every
  attempt file it does not return, and the caller deletes the returned
  frame plus the empty placeholder in its `finally` block.
- **Read-only files can be moved.** Windows cannot delete a file whose
  read-only attribute is set, so transferring such a file failed at the
  final `unlink()` — or, worse, left a stray copy inside the category
  folder and another one on every retry. The new `force_unlink()` helper
  clears the read-only attribute and retries; it is now used for the
  source deletes in both move paths (hardlink and copy+delete) and for
  the destination cleanups.
- **Category paths must be absolute.** A relative path typed into the
  category dialog (e.g. `Photos`) silently resolved against whatever
  folder the app happened to be started from, scattering files in
  unpredictable places. The dialog now rejects relative paths with a
  bilingual warning (`~`-paths are still accepted after expansion).

### Build hardening
- **The portable package only ever contains pinned, hash-verified
  runtimes.** `build_deps.ps1` no longer reuses a `bin\vlc` folder, an
  installed VLC from Program Files, or a pre-existing `bin\7za.exe` —
  all three had unknown version/license provenance and skipped the
  SHA-256 check. The pinned downloads (cached in `build\_downloads`) are
  now the only source, re-verified on every build, for VLC 3.0.21,
  7-Zip 26.05 and ffmpeg 7.1.1 alike. The unused `Copy-FirstCommand` /
  `Copy-IfDifferent` helpers were removed.
- **Licence notice completed:** `THIRD_PARTY_NOTICES.md` now also lists
  the Qt 6 libraries and the FFmpeg media backend that ship inside the
  PyQt6 wheels (both are bundled into the exe by `--collect-all PyQt6`)
  with their LGPL licences and source links.

### Removed
- **The dev-only `tests/` sandbox is no longer part of the published
  repository** (now listed in `.gitignore`). Releases are validated by
  the pre-release checklist instead.

## [1.9.2] — Lock-file & cancel-undo fixes

Two fixes. No UI changes.

### Fixed
- **`python-vlc==3.0.21` does not exist on PyPI** (regression in the
  v1.9.1 lock file). PyPI only publishes `3.0.21201` / `3.0.21203` for
  the VLC 3.0.21 bindings, so `BUILD.bat` — which now prefers
  `requirements-lock.txt` — failed at the dependency-install step on
  every machine. The pin is now `python-vlc==3.0.21203` (the current
  release; verified with `pip install --dry-run`), and the "Tested with"
  comment in `requirements.txt` was corrected the same way.
- **Undo regression: cancelling while transfers were still queued** left
  the undo batch open forever, so the Undo button stayed disabled and
  Ctrl+Z said "Nothing to undo" until the next transfer round merged the
  batch. Cause: `cancel_all()` emits `queue_updated(0, 0)` *synchronously
  inside itself* — before the caller fixed up the expected-count — so the
  seal-check correctly saw `done < expected` and refused, and no further
  signal ever arrived when nothing was running. `_cancel_all_transfers()`
  now re-runs the seal check after the count fix-up (new
  `TransferManager.is_idle()` helper); batches with still-running futures
  continue to close through their own finished/error events, exactly as
  before.
- **PyInstaller is now pinned** (`pyinstaller==6.22.3`) in `BUILD.bat`,
  which previously installed it unpinned — the one remaining unpinned
  piece of the build chain.

### Added
- `tests/test_transfer_undo.py` — the project's first automated test
  file (pytest, also runnable standalone with `python
  tests/test_transfer_undo.py`). It covers the cancel-undo regression
  above (the new test fails on the v1.9.1 code and passes now), the
  undo-batch race end to end (40 concurrent files → all recorded in the
  batch → undo restores every one), plus core helpers:
  `unique_destination`, `parse_extension_filter`,
  `normalize_categories`, the `.ts` sync-byte sniff and the atomic
  `config.json` save/corrupt-backup behaviour. Headless-safe:
  `QT_QPA_PLATFORM=offscreen`, config isolated per test and modal
  dialogs auto-answered so a popup can never hang a CI run.

## [1.9.1] — Release-readiness fixes

Bug-fix release. No UI changes — everything below is packaging, safety
and robustness.

### Fixed
- **ffmpeg licence actually ships now.** Inside the pinned ffmpeg 7.1.1
  zip the licence file is named `LICENSE` with **no extension**, but
  `build_deps.ps1` searched for `LICENSE*.txt` — the filter never matched,
  the `if` silently skipped, and `ffmpeg-LICENSE.txt` was never created
  even though `THIRD_PARTY_NOTICES.md` promised it (a real GPL-compliance
  gap for the distributed binaries). The filter is now `LICENSE*` (also
  `README*`), and a missing file **fails the build** instead of being
  skipped silently. `BUILD.bat` additionally verifies that
  `ffmpeg-LICENSE.txt` / `ffmpeg-README.txt` exist in `_internal\bin`
  before declaring the build a success.
- **"Open with system player" no longer bypasses the program warning.**
  Double-clicking an executable asked for confirmation, but the
  "Open with system player" button opened the very same `.exe`/`.bat`/`.ps1`
  files without any check. Both paths now share one
  `_confirm_run_executable()` helper, so the bilingual
  "This file looks like a program" dialog covers every way the app can
  hand a file to Windows.
- **Crash-safe settings file.** `config.json` is now written atomically
  (temp file + `os.fsync` + `os.replace`), so a crash or power loss during
  a save can no longer leave a half-written file that wipes the user's
  categories on the next start. If the config is ever unreadable, it is
  moved to `config.json.corrupt` (recoverable) and the incident is logged
  in `app.log`; save failures are logged too instead of being swallowed.
- **Undo race closed.** The undo batch was sealed as soon as the transfer
  queue reported `(queued=0, active=0)` — but that signal can also come
  from the manager's 150 ms tick between a worker thread popping the last
  future and the UI processing that file's `transfer_finished` event. In
  that window the last file of the round was locked out of Ctrl+Z. The
  batch is now sealed only when every file it expected has reported back
  (finished *or* failed), and "Cancel all" subtracts the files it dropped
  from the queue so the batch can still close.
- **`.ts` files are no longer treated as video on faith.** The extension
  belongs to both MPEG Transport Stream video and TypeScript source; the
  video branch always won, so TypeScript files got the video player (and
  an ffmpeg probe) on click. Now the first bytes are checked — real
  MPEG-TS starts with the 0x47 sync byte repeated every 188 bytes — and
  anything else behaves like source code. Real `.ts` recordings still
  play exactly as before.
- **BUILD.bat contradiction resolved.** It passed `--hidden-import
  PySide6.QtMultimedia[Widgets]` *and* `--exclude-module PySide6` at the
  same time; the two PySide6 hidden-import lines are gone.
- `hashlib.sha1(..., usedforsecurity=False)` for the thumbnail cache key —
  it was never a security primitive, and bandit's lone "High" finding is
  gone.

### Added
- `requirements-lock.txt` with the exact tested versions; `BUILD.bat`
  prefers it over `requirements.txt`, so every release is built from the
  same dependency set. The stale python-vlc comment in `requirements.txt`
  was corrected (the portable build bundles VLC; only dev machines need an
  install).
- `SECURITY.md` pointing vulnerability reports at GitHub's private
  vulnerability reporting instead of public issues (with a Persian note).
- `THIRD_PARTY_NOTICES.md` now links the **exact** upstream sources of the
  bundled binaries (ffmpeg 7.1.1 tarball, VLC 3.0.21 tarball) instead of
  the generic download pages, and its notes correctly describe the
  ffmpeg `LICENSE` file (no extension) inside the zip.

### Changed
- READMEs state plainly that **PyQt6 is the only tested/supported
  binding** (PySide6/PyQt5 fallback branches exist but are untested), and
  document the new lock-file builds.

## [1.9.0] — One merged category panel & publish-prep fixes

### Added
- **Merged category panel.** The right panel used to show every category
  twice — a plain list at the top and a row of quick move buttons below —
  which wasted vertical space and made the two views feel redundant. The
  list is gone: every category is now a single button in one scrollable
  column. Clicking a button still moves the selected files into that
  category; **right-clicking** it opens a menu with **Edit**, **Remove**,
  **Move up** and **Move down** (this replaces both the old Add/Edit/Remove
  button row and the "Swap two buttons" dialog). The number of categories
  is still unlimited and every button stays clickable, but only the first
  ten carry the `0:`–`9:` badge and the digit shortcuts — a `12:` badge
  would suggest a key that does nothing, so categories beyond ten show
  their plain name. Fully bilingual, and the hint above the list explains
  the click / right-click roles in both languages.

### Changed
- **Publish-prep licence & packaging fixes**:
  - `assets/OFL.txt` — the complete SIL Open Font License 1.1 text now
    ships next to `Vazirmatn-Regular.ttf` (the OFL requires the licence
    text to accompany the font), and `THIRD_PARTY_NOTICES.md` links it.
  - `.gitattributes` — `*.bat`/`*.ps1` are forced to CRLF (cmd.exe can
    misparse LF-only batch files), PNG/GIF/TTF are marked binary, and text
    files are normalized.
  - `build_deps.ps1` now always uses the pinned, hash-verified ffmpeg
    7.1.1 build — the system-PATH ffmpeg is no longer copied in, so builds
    are reproducible — and copies that build's own `LICENSE.txt` /
    `README.txt` into the portable zip as `ffmpeg-LICENSE.txt` /
    `ffmpeg-README.txt` (GPL compliance for the distributed binaries).
    VLC 3.0.21 and ffmpeg 7.1.1 now link their exact pinned sources in
    `THIRD_PARTY_NOTICES.md`.
  - The README technical-notes sentence was corrected: not every
    subprocess call uses `--` (the ffmpeg calls do not); the real
    guarantee is "list arguments, never shell=True".
  - Version badges and release notes point to 1.9.0.

## [1.8.0] — Undo for transfers & clearer READMEs

### Added
- **Undo (`Ctrl+Z` / «Undo move» button).** Every completed transfer round
  is recorded as (source, destination) pairs as it finishes; pressing
  `Ctrl+Z` or clicking the new **Undo move** button (right panel, above the
  progress bar) moves those files back to their original folder — in a
  background thread, never overwriting anything (if the original slot is
  taken again meanwhile, the file is restored beside it under a unique
  name) — and then rescans the folder so the files reappear in the
  explorer grid. The button stays disabled while there is nothing to undo;
  `Ctrl+Z` inside a text field still undoes the typed text; undoing a
  transfer that used the automatic `name (1).ext` rename restores the
  original name. Files that cannot be restored (deleted from the category
  folder meanwhile) stay where they are, are reported, and the next undo
  retries them. Fully bilingual: the button, tooltips and all status
  messages are translated (برگرداندن انتقال، در حال برگرداندن آخرین
  انتقال، ...).

### Fixed
- **Mixed-direction category labels no longer flip in the Persian UI.** A
  label like `0: Photos` used to render as `Photos :0` in the RTL layout;
  the category list and quick-button labels are now wrapped in U+2066 /
  U+2069 isolates so "0:" stays in front of the name regardless of the
  interface language (a Persian name still renders naturally).

### Changed
- **READMEs clarified.** The English README now links the Persian version
  as «فارسی» (and the language feature bullet mentions it too). Both
  READMEs now state plainly that the number of categories is **unlimited**
  and only the first ten get quick buttons and `0`–`9` shortcuts — the
  old Quick-start wording read as if only ten categories could exist — and
  the heads-up box plus the "moved a file to the wrong category" FAQ now
  describe the undo instead of claiming moves are irreversible. The
  Persian README copyright line now reads "Mohammad Jafari" in English
  letters to match the GitHub username, and the code headers (main.py,
  app_i18n.py) use the same spelling. Version badges and the "current
  release" notes point to 1.8.0.

## [1.7.0] — Six distinct themes, compact header pickers & UI polish

### Changed
- **Dim removed, three new themes added.** A colour-distance (ΔE) check
  showed Dim was practically identical to Dark (ΔE 2.3 on the background,
  5.4 on the panel — below the ~10 threshold where eyes can tell colours
  apart; it only differed by its blue accent). Dim is gone; **Paper**
  (warm light), **Graphite** (neutral dark, teal accent) and **Forest**
  (green dark) replace it. The picker now offers six visually distinct
  themes ordered light → dark: Light, Paper, Graphite, Dark, Forest,
  AMOLED. A config that still saves `"dim"` falls back to Dark with no
  error. The muted text colours of Light and Paper were darkened slightly
  (to `#4f5965` / `#5a503c`) so every theme now keeps muted text at
  ≥ 6:1 and main text at ≥ 11:1 contrast.
- **Theme & language moved from segmented buttons to two compact dropdowns.**
  With six themes the old button row grew past 700 px (≈ 39 % of the window
  width); the header chip now holds two combos (~300 px). Every theme item
  shows a two-colour circle — half theme background, half accent — so the
  palette is visible before choosing. Item texts are re-translated live on
  language switch (`setItemText`, keyed by item data, same idea as the old
  `_theme_key`).
- **AMOLED accent fixed for contrast.** White text on the AMOLED accent
  reached only ~3.9:1, and the PrimaryBtn hover colour (`#5ac8fa`, cyan)
  only 1.9:1. AMOLED is now `accent #6a5af0` (4.85:1) and
  `accent2 #5a49e0` (6.06:1). The Dark theme's panel borders and selection
  were strengthened (`border #34455f`, `sel #22344f`) so panels separate
  from the background instead of melting into it.

### Added
- **`danger_bg` token.** The danger button's hover fill used to reuse the
  red *text* colour, which is too bright for white text on hover
  (3.0–3.8:1). Each theme now carries a separate, darker `danger_bg`
  (`#dc2626`, `#b91c1c`, `#991b1b`-grade values) used for the hover fill —
  white text stays ≥ 4.5:1 everywhere.
- **Themed scrollbars.** Slim 10 px scrollbars with rounded handles
  (border colour, muted on hover, invisible arrows/pages) replaced the
  bright system scrollbars that clashed with every dark panel.
- **Visible keyboard focus & disabled states.** The global
  `outline: none` killed the system focus ring; focused buttons now show
  an accent border (accent-filled buttons get a text-coloured one so the
  ring is visible on accent backgrounds), and disabled buttons, inputs and
  combos have explicit muted styles instead of palette guesses.
- **Painted combo arrows (`HeaderCombo`).** With
  `QComboBox::drop-down { border: none }` Qt drew no arrow at all — every
  combo looked like a text field. The new `HeaderCombo` paints a real,
  theme-coloured triangle in `paintEvent` (no image files, works in the
  frozen exe, respects RTL placement); it is used for the theme, language
  and sort pickers.
- **Startup focus on the file grid.** The theme combo was the first
  focusable widget in the window and silently swallowed the `0`–`9`
  shortcuts (the guard treats a focused combo as a text field) until the
  user clicked somewhere. The grid gets the initial focus now, and picking
  a theme or language hands the keyboard back to the grid — never while
  the popup is still being arrow-navigated.

### Fixed
- **"+ Add Category" was clipped.** The button lived *inside* the quick
  buttons' scroll area and got cut in half / scrolled out of sight as the
  category list grew. It now sits below the scroll area, always fully
  visible, and is retranslated like every other control.
- **Progress bar stuck at 100 %.** After a scan the bar stayed full
  forever while idle, which read as a stuck transfer. It now hides when
  idle and only shows (as an indeterminate busy bar) while scanning.

## [1.6.0] — Audio playback & dialogs that match the theme

### Added
- **Audio playback.** Audio files (`mp3`, `wav`, `flac`, `aac`, `ogg`, `opus`,
  `m4a`, `wma`) used to be preview-only — selecting one showed its type card
  and the Play button did nothing. Audio now plays through the same embedded
  Qt Multimedia engine as videos (the bundled FFmpeg backend decodes it; no
  extra runtime), starts automatically on selection, loops like videos
  (`setLoops(-1)`), and the Play/Pause + Stop buttons work on it. The audio
  type card stays visible while the sound plays. If the embedded engine is
  unavailable, the bundled `ffplay` fallback plays it with `-nodisp` (pure
  sound, no spectrum window), and a decoder error hands the file to the next
  engine instead of dying silently.
- **Persian theme names.** The four theme buttons now show translated
  labels in the Persian UI (Dark/Dim/AMOLED/Light become their Persian
  names), matching the rest of the translated interface; the underlying
  theme keys and saved config are unchanged.

### Fixed
- **Dialogs no longer break the theme.** The generic `QWidget` stylesheet
  rule gave every `QLabel` an opaque background-coloured rectangle, so in the
  Add/Edit Category, Save/Load set and Swap dialogs the text sat on boxes of
  a slightly different colour than the dialog itself. Labels are transparent
  now (`QLabel`, `QDialog QLabel`, `QInputDialog QLabel`). On top of that the
  whole **QPalette** follows the selected theme — with Fusion on Windows
  every widget the stylesheet does not explicitly cover (spin boxes in the
  Swap dialog, disabled text, native popups) used to fall back to the light
  system palette. New rules style `QSpinBox`, the `QListView` used by
  "Load set" and small check indicators.
- **Dark title bars on Windows.** Windows paints dialog title bars from the
  SYSTEM theme, never from the app — so dark-themed dialogs got white title
  bars. The app now tells the platform theme it is dark via
  `QStyleHints::setColorScheme` (Qt >= 6.8, which `requirements.txt`
  already requires — this covers every window, dialogs and message boxes
  included) and additionally applies `DWMWA_USE_IMMERSIVE_DARK_MODE` to the
  main window, so the chrome matches the theme; light theme keeps light
  chrome. Non-Windows platforms are untouched.
- **README screenshots existed only as broken links.** `docs/` was missing
  from the repo, so `README.md` / `README.fa.md` showed broken images. Real
  captures of the app (`docs/screenshot-en.png`, `docs/screenshot-fa.png`,
  dark theme, EN + FA/RTL) are now part of the repo.

### Documentation
- **Both READMEs restructured for end users.** New *Download & Install*
  section (Releases link, extraction steps, Windows 10/11 x64 requirement,
  SmartScreen explanation, checksum note), a four-step *Quick start* with an
  explicit "moves are permanent, there is no undo" warning, a shortened
  one-line-per-feature list, a *FAQ & common problems* section, a
  "where is my data stored" section, and all developer content (run from
  source, build, technical notes, project structure) grouped at the bottom.
  The in-README "What's new" sections were removed — the READMEs now link
  to `CHANGELOG.md` instead. The Persian text was rewritten to read more
  naturally.
- **Demo GIFs.** `docs/demo-en.gif` / `docs/demo-fa.gif` are real captures
  of the app: a file is selected, a number key is pressed, the file moves
  into the matching category and the status bar reports the result.
- **BUILD.bat** now writes a `SortView-win64-portable.zip.sha256` checksum
  file next to the zip, so the release page can publish a verifiable hash.

## [1.5.0] — Looping videos, honest Play/Pause button & short-clip thumbnails

### Fixed
- **Very short videos (< 1 s) had no thumbnail.** The ffmpeg frame grab was
  hard-coded to the 1-second mark, so clips shorter than that produced no
  frame and fell back to a type card. The extractor now retries at 0.4 s and
  then at the very first frame; sub-second clips get a real thumbnail now.
- **The Play/Pause button lied after a clip ended.** Nothing updated the
  button when the video finished, so it stayed on "Pause" and pressing it
  restarted the video — it looked like pause = replay. A 0.4 s sync timer
  plus instant Qt `playbackStateChanged`/end signals keep the label in sync
  with the real engine state (Qt and VLC), and the VLC pause/resume now uses
  `get_state()` + explicit `set_pause()` instead of the ambiguous toggle.
- **Two players could overlap.** Pressing Play while the external `ffplay`
  fallback was running started an embedded player on top of it. The external
  player is stopped first now, and the button label reflects that pressing
  it takes over playback in the embedded player.

### Changed
- **Videos loop in every engine.** Qt Multimedia loops via `setLoops(-1)`
  (with a manual `EndOfMedia` → rewind fallback), libVLC gets
  `input-repeat=65535` on its media, and the bundled `ffplay` fallback is
  launched with `-loop 0`. When a clip ends, it restarts from the beginning.
- **The "include subfolders (recursive)" checkbox is now a highlighted
  card** in the folder dialog: bigger accent-colored indicator, pointer
  cursor, bold label and a one-line hint explaining exactly what checking
  it does (bilingual). A bare checkbox row there was too easy to miss.

## [1.4.0] — Video display fix, real icons & unified header

### Fixed
- **Videos never displayed.** `QtVideoWidget` created its `QVideoWidget` but
  never called `QMediaPlayer.setVideoOutput()`, so the audio played while the
  picture stayed black. The output is bound now, and a stronger health check
  (`mediaStatus`/`error`, not just "source is set") triggers the automatic
  VLC / `ffplay.exe` fallbacks when a video really cannot be decoded.
- `_first_image_from_7zip_cli` iterated a list of dicts as if it were a list
  of tuples, so archive thumbnails through the 7za fallback always aborted
  with a `TypeError` on the first entry.

### Changed
- **All 30 file-type icons redrawn** as real document-style icons (white page
  with folded corner, colored label with the extension, per-type glyph).
  They are original artwork **generated with AI** for this project — no
  third-party icon sets and no brand logos (stated in both READMEs and
  `THIRD_PARTY_NOTICES.md`). Known extensions now show the icon itself in
  the grid instead of the old gradient card.
- **Header redesigned:** theme (Dark/Dim/AMOLED/Light) and language
  (English/فارسی) are exclusive segmented buttons inside one themed chip —
  same accent color and corner radius as the rest of the UI — plus the app
  icon next to the window title. Stylesheets extended for dialogs, message
  boxes, status bar labels, danger-button hover and slider handles.
- New **"Open with system player"** button in the preview panel; when no
  video engine is available the preview shows the frame with a play badge
  and the status bar explains exactly what to install (bilingual).
- `requirements.txt` requires `PyQt6>=6.9` (wheels that include the
  QtMultimedia engine); `BUILD.bat` verifies the import in the build venv
  and self-heals if missing.

### Security
- `build_deps.ps1` re-verifies the SHA-256 of cached 7-Zip downloads
  (`7zr.exe`, `7z2605-extra.7z`) exactly like ffmpeg/VLC, so a tampered
  cache cannot reach the portable zip.

## [1.3.0] — Built-in video engine, UI polish & safer previews

### Added
- Embedded video playback now runs on **Qt Multimedia** (the media engine
  that ships inside the PyQt6/PySide6 wheels) — videos play inside the window
  with **no VLC installation needed**; libVLC and the bundled `ffplay.exe`
  remain as automatic fallbacks.
- A bilingual confirmation appears before opening files that look like
  programs (`.exe`, `.bat`, `.ps1`, ...).
- All 30 file-type icons were redrawn as **original artwork** created for
  SortView (no brand logos, no third-party icon packs).

### Changed
- Interface polish: theme & language controls sit in a matching header chip;
  dropdown popups, menus, checkboxes and message boxes follow the active
  theme — a calmer, eye-friendly look.
- `build_deps.ps1` pins exact tool versions (ffmpeg 7.1.1, VLC 3.0.21,
  7-Zip 26.05) and verifies every download against its official SHA-256
  before anything enters the portable zip.

### Security
- Decompression-bomb guard: `PIL.Image.MAX_IMAGE_PIXELS` capped at 64 MP.
- Archive previews skip entries larger than 64 MB instead of reading them
  fully into memory.
- `7za` receives `--` before user-controlled paths, so archive entries whose
  names start with `-` can no longer be parsed as switches.

## [1.2.0] — Bilingual UI (English / Persian)

### Added
- Fully bilingual interface: **every** window, dialog, button, status message
  and tooltip is available in English and Persian (new `app_i18n.py`
  translation module, ~120 strings).
- First launch automatically follows the OS display language; a new
  **Language** combo in the header switches the whole UI instantly — no
  restart needed.
- Persian mode flips the layout to right-to-left (`RightToLeft`), so menus,
  panels and dialogs mirror correctly.
- The chosen language is persisted in `user_data/config.json`
  (`"language": "en" | "fa"`), so the app always reopens the way you left it.

### Changed
- Entry point renamed `untitled0.py` -> `main.py` (`BUILD.bat`, `run.bat` and
  docs updated accordingly).
- Application renamed: **File Sorter & Viewer** -> **SortView** (سورت‌ویو) —
  window title, exe name (`SortView.exe`), portable zip name and the
  read-only user-data fallback folder (`%LOCALAPPDATA%\SortView`) updated.
- New application icon (`assets\icon.png`): white folder with three colored
  sorting arrows on a blue-violet rounded square.
- Copyright holder updated to mohammad jafari (mohammadjafari-dev).
- `LICENSE` and `THIRD_PARTY_NOTICES.md` are now bundled inside the portable
  package (GPL compliance for the distributed zip).
- GPL copyright header added to the sources; copyright line added to the
  READMEs.
- `import pymupdf` replaces the deprecated `import fitz` (old name still
  accepted as a fallback).
- README archive-thumbnail claim corrected: `.rar` previews need an external
  unrar tool (7za cannot open RAR); the app shows a type card instead.
- `user_data\` creation no longer crashes when the install folder is
  read-only (falls back to `%LOCALAPPDATA%`).
- requirements.txt records the tested dependency versions.
- Sort combo logic is now index-based; translated "Name/Type" labels no
  longer affect sorting (which also accepts the legacy `"نوع"` value).
- Runtime errors from the transfer worker (cancelled, missing source, ...)
  are translated before they reach the status bar.

## [1.1.0] — Speed, first-launch & playback fixes

### Fixed
- No path is created or guessed on first launch anymore (the old
  `Desktop\to_sort` default is fully removed). A stored folder is only
  restored when the config explicitly has `folder_user_selected=true`, so
  stale configs from older versions are ignored.
- `last_browse_dir` is remembered in `config.json`; the folder dialog,
  category Browse and Import/Export all reopen at the last directory you
  picked.
- Crash when transferring a file (especially videos): the preview and VLC
  playback are fully stopped and the media handle released, then the real
  move is enqueued after a short (~200 ms) delay so libVLC lets go of the
  file on Windows.
- Number keys `0`–`9` and the category quick buttons fire exactly once —
  `QShortcut.setAutoRepeat(False)` plus a short debounce, so holding a key
  no longer moves several files in a row.

### Improved
- Thumbnail pipeline reworked like faster viewers: visible files have the
  highest priority, near-viewport files medium, everything else streams in
  from the background queue; files you scroll to are re-prioritized to the
  front.
- Parallelism tuned to CPU count (workers, batch size, video thumbs);
  every ffmpeg thumbnail runs with `-threads 1` and low priority so the UI
  never locks up. No more `ffprobe` call per video file — a single fast
  frame around second 1.
- Video auto-plays when a video is selected; if the embedded VLC only gives
  audio or fails to attach the surface, the app falls back to bundled
  `ffplay.exe` after a few moments.
- Type cards are cached in RAM; `ffmpeg/ffprobe/ffplay/7za` run without
  flashing terminal windows.

## [1.0.0] — Initial release

- Thumbnail grid browser with filters, Name/Type sorting and thumbnail size
  slider.
- Previews: images, animated GIFs, video playback (embedded VLC), PDF first
  pages, type cards, archive first-image thumbnails.
- Category management (add/edit/remove, save/load/swap sets, import/export
  JSON) with 0–9 shortcuts.
- Safe background transfer manager (hardlink → exclusive copy → source
  delete, unique names, cancel support).
- 4 themes, Vazirmatn font, fully portable `user_data\` layout.
- Windows portable build via `DOWNLOAD_PORTABLE_DEPS.bat` + `BUILD.bat`
  (PyInstaller, bundled ffmpeg/VLC/7-Zip).
