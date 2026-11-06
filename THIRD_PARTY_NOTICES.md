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
| [FFmpeg](https://ffmpeg.org/) (`ffmpeg.exe`) | video thumbnails (bundled in `bin\`, license text shipped as `ffmpeg-LICENSE.txt` / `ffmpeg-README.txt`) | **GPL v3** — the pinned build is configured with `--enable-gpl --enable-version3` and links GPL codec libraries (libx264, libx265, libxvidcore, libaom) | pinned 7.1.1 essentials build (SHA-256 verified): [release page with the full library list](https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1) · [ffmpeg source tarball](https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz) |
| [py7zr](https://github.com/miurahr/py7zr) | reading `.7z` archives | LGPL-2.1-or-later | bundled via pip |
| [multivolumefile](https://github.com/miurahr/multivolumefile) | py7zr dependency (multi-volume archive support) | LGPL-2.1-or-later | bundled via pip |
| [pyppmd](https://github.com/miurahr/pyppmd) | py7zr dependency (PPMD compression codec) | LGPL-2.1-or-later | bundled via pip |
| [pybcj](https://github.com/miurahr/pybcj) | py7zr dependency (BCJ branch filters) | LGPL-2.1-or-later | bundled via pip |
| [inflate64](https://github.com/miurahr/inflate64) | py7zr dependency (deflate64 decompression) | LGPL-2.1-or-later | bundled via pip |
| [brotli](https://github.com/google/brotli) | py7zr dependency (Brotli-compressed entries) | MIT | bundled via pip |
| [pycryptodomex](https://pycryptodome.readthedocs.io/) | py7zr dependency (encrypted archives) | BSD, Public Domain | bundled via pip |
| [psutil](https://github.com/giampaolo/psutil) | py7zr dependency (memory checks) | BSD-3-Clause | bundled via pip |
| [rarfile](https://github.com/markokr/rarfile) | reading `.rar` archives | ISC | bundled via pip |
| [Python 3.13](https://www.python.org/) (`python313.dll` embedded in the exe by PyInstaller) | the runtime the exe carries | PSF License Version 2 | [source](https://www.python.org/downloads/source/) |
| [OpenSSL 3.x](https://www.openssl.org/) (`libcrypto-3-x64.dll` / `libssl-3-x64.dll` shipped next to the exe by PyInstaller) | crypto backend of Python's `ssl` / `hashlib` | Apache-2.0 | [source](https://github.com/openssl/openssl) |
| [Vazirmatn font](https://github.com/rastikerdar/vazirmatn) (`Vazirmatn-Regular.ttf`) | UI font | SIL Open Font License 1.1 — full text bundled in [`assets\OFL.txt`](assets/OFL.txt) | bundled in `assets\` |
| [PyInstaller](https://pyinstaller.org/) | packaging into a portable exe — its bootloader is embedded in `SortView.exe` | GPL-2.0-or-later with a bootloader exception that permits distributing the embedded bootloader | [source](https://github.com/pyinstaller/pyinstaller) |

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
- The bundled ffmpeg build includes a corresponding source offer: the
  ffmpeg tarball link in the table points at the exact source version of
  the binary inside the portable zip (ffmpeg 7.1.1). Note that the pinned
  *essentials* build links GPL codec libraries (libx264, libx265,
  libxvidcore, libaom) whose sources are not part of that tarball; the
  upstream sources of those libraries are listed on the linked GyanD
  release page, and each library's own upstream repository provides its
  source.
- The portable exe also contains the Qt 6 libraries and the FFmpeg media
  backend that come inside the PyQt6 wheels (`--collect-all PyQt6`). Both
  are LGPL-licensed and dynamically usable without releasing this
  project's own source under the LGPL; their sources are reachable via the
  links in the table (download.qt.io / code.qt.io / ffmpeg.org).
- The project's choice of GPL v3 is driven by PyQt6 (GPL v3) and PyMuPDF
  (AGPL v3), which the executable bundles. See [`LICENSE`](LICENSE) for the
  full license text.
