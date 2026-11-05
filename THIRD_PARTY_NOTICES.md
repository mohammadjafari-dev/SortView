# Third-Party Notices

This project, **SortView (سورت‌ویو)**, is licensed under the
**GNU General Public License v3.0 or later** — see [`LICENSE`](LICENSE).

It is built on top of the following third-party components. Each one keeps its
own license, listed here together with its source location:

All application and file-type icons in `assets\` (including `assets\icon.png`)
are **original artwork generated with AI** specifically for this project —
no third-party icon packs and no brand logos are bundled.

| Component | Role in this app | License | Source |
|---|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GUI framework | GPL v3 (or Riverbank commercial license) | bundled via pip |
| [Qt 6](https://www.qt.io/) (the C++ Qt libraries shipped inside the PyQt6 wheels, bundled into the exe by `--collect-all PyQt6`) | GUI runtime | LGPL v3 (some modules alternatively GPL v3; or Qt commercial license) | [Qt sources](https://download.qt.io/official_releases/qt/) · [Qt code browser](https://code.qt.io/cgit/) |
| [FFmpeg](https://ffmpeg.org/) inside Qt Multimedia | media backend of the built-in video player (`PyQt6.QtMultimedia`, ships inside the Qt Multimedia wheel) | LGPL-2.1-or-later | [FFmpeg source](https://ffmpeg.org/download.html) · [Qt Multimedia sources](https://code.qt.io/cgit/qt/qtmultimedia.git/) |
| [PySide6](https://www.qt.io/qt-for-python) *(optional alternative Qt binding)* | GUI framework | LGPL v3 | bundled via pip |
| [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) | PDF thumbnails & rendering | AGPL v3 (or Artifex commercial license) | bundled via pip |
| [Pillow](https://python-pillow.org/) | image decoding / type cards | MIT-CMU (HPND) | bundled via pip |
| [FFmpeg](https://ffmpeg.org/) (`ffmpeg.exe`) | video thumbnails (bundled in `bin\`, license text shipped as `ffmpeg-LICENSE.txt` / `ffmpeg-README.txt`) | FFmpeg is LGPL-2.1-or-later / GPL depending on build configuration; the pinned 7.1.1 *essentials* build includes GPL components | pinned 7.1.1 essentials build (SHA-256 verified): [release](https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1) · [source of these binaries](https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz) |
| [py7zr](https://github.com/miurahr/py7zr) | reading `.7z` archives | LGPL-2.1-or-later | bundled via pip |
| [rarfile](https://github.com/markokr/rarfile) | reading `.rar` archives | ISC | bundled via pip |
| [Vazirmatn font](https://github.com/rastikerdar/vazirmatn) (`Vazirmatn-Regular.ttf`) | UI font | SIL Open Font License 1.1 — full text bundled in [`assets\OFL.txt`](assets/OFL.txt) | bundled in `assets\` |
| [PyInstaller](https://pyinstaller.org/) *(build-time only, not distributed)* | packaging into a portable exe | GPL with bootloader exception | bundled via pip |

## Notes for distributors

- If you build and distribute the portable package
  (`SortView-win64-portable.zip`), the licenses above apply to the
  corresponding bundled components.
- The portable zip carries the license texts of everything inside it:
  the app ships `LICENSE` + `THIRD_PARTY_NOTICES.md`, the pinned ffmpeg
  build's `LICENSE` (that file has no extension inside the ffmpeg zip) and
  `README.txt` are staged as `ffmpeg-LICENSE.txt` / `ffmpeg-README.txt`,
  and the Vazirmatn font ships with its full OFL 1.1 text in
  `assets\OFL.txt`.
- Runtime versions are pinned and their SHA-256 is verified in
  `build_deps.ps1` before anything is packaged (ffmpeg 7.1.1 essentials
  build from GyanD releases — the only bundled binary since v1.10.3).
  The pinned, hash-verified download is the ONLY source: a system-PATH
  ffmpeg or a pre-existing `bin\` copy is never reused, so builds stay
  reproducible.
- The bundled ffmpeg build includes a complete corresponding source offer:
  the source link in the table points at the exact tarball of the version
  inside the portable zip (ffmpeg 7.1.1) — the same version as the binary,
  not just the project homepage.
- The portable exe also contains the Qt 6 libraries and the FFmpeg media
  backend that come inside the PyQt6 wheels (`--collect-all PyQt6`). Both
  are LGPL-licensed and dynamically usable without releasing this
  project's own source under the LGPL; their sources are reachable via the
  links in the table (download.qt.io / code.qt.io / ffmpeg.org).
- The project's choice of GPL v3 is driven by PyQt6 (GPL v3) and PyMuPDF
  (AGPL v3), which the executable bundles. See [`LICENSE`](LICENSE) for the
  full license text.
