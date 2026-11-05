#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# SortView (سورت‌ویو) — fast thumbnail browsing and safe file sorting.
# Copyright (C) 2026 Mohammad Jafari (mohammadjafari-dev)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
# ----------------------------------------------------------------------------
"""
SortView — Qt6 edition

یک ابزار دسکتاپ برای مرور سریع فایل‌ها و انتقال امن آن‌ها به پوشه‌های دسته‌بندی.
نسخه‌ی فعلی ابتدا PyQt6 را استفاده می‌کند؛ اگر نصب نبود، برای سازگاری PySide6 و
در نهایت PyQt5 را هم می‌پذیرد. پخش ویدیو و صدا با موتور چندرسانه‌ای Qt انجام
می‌شود (بک‌اند FFmpeg داخل خود PyQt6) — بدون VLC و بدون ffplay. ظاهر و کارت‌های
نوع فایل اختصاصی همین پروژه است و همه‌ی آیکون‌های
پوشه‌ی assets نیز اثر اصلی و تازه‌ساخته‌ی همین پروژه هستند (بدون لوگوی برندها).

Bilingual UI (English / Persian) lives in app_i18n.py: the first run follows
the OS display language, the header combo switches instantly (with RTL for
Persian) and the choice is persisted in user_data/config.json.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from shutil import which
from typing import Iterable, List, Optional, Tuple

import app_i18n
from app_i18n import t

# -----------------------------------------------------------------------------
# Qt binding: prefer PyQt6, then PySide6, then PyQt5 as a compatibility fallback.
# NOTE: only PyQt6 is tested, shipped and supported. The PySide6/PyQt5 branches
# exist so the source still starts on other machines, but bugs reported against
# them are out of scope (see README — PyQt6 >= 6.9 is the supported binding).
# -----------------------------------------------------------------------------
try:  # Preferred
    from PyQt6 import QtCore, QtGui, QtWidgets
    Signal = QtCore.pyqtSignal
    QT_API = "PyQt6"
    QT6 = True
except Exception:
    try:  # Also Qt6 and API-wise very close
        from PySide6 import QtCore, QtGui, QtWidgets
        Signal = QtCore.Signal
        QT_API = "PySide6"
        QT6 = True
    except Exception:  # Untested last-resort fallback — not supported, see README.
        from PyQt5 import QtCore, QtGui, QtWidgets
        Signal = QtCore.pyqtSignal
        QT_API = "PyQt5"
        QT6 = False

Qt = QtCore.Qt
QTimer = QtCore.QTimer
QSize = QtCore.QSize
QUrl = QtCore.QUrl
QPixmap = QtGui.QPixmap
QImageReader = QtGui.QImageReader
QMovie = QtGui.QMovie
QIcon = QtGui.QIcon
QKeySequence = QtGui.QKeySequence
QDesktopServices = QtGui.QDesktopServices
QShortcut = getattr(QtGui, "QShortcut", getattr(QtWidgets, "QShortcut", None))

# Video and audio playback, the one bundled engine: Qt Multimedia. It ships
# inside the PyQt6/PySide6 wheels (FFmpeg backend included), so media plays
# in-app with NO VLC, no ffplay and no other external runtime. The dormant
# libVLC/ffplay branches below only wake up on dev machines that happen to
# have python-vlc or ffplay installed; the portable build ships none of them.
if QT_API == "PyQt5":
    HAS_QTMEDIA = False
    QTMEDIA_IMPORT_ERROR = "Qt Multimedia is not available on PyQt5"
else:
    try:
        if QT_API == "PyQt6":
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        else:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
        HAS_QTMEDIA = True
        QTMEDIA_IMPORT_ERROR = ""
    except Exception as _qtmedia_exc:
        HAS_QTMEDIA = False
        QTMEDIA_IMPORT_ERROR = f"{type(_qtmedia_exc).__name__}: {_qtmedia_exc}"

def _qt_value(owner, enum_name: str, member_name: str, legacy_name: Optional[str] = None, default=None):
    """Return Qt6 enum member if present, otherwise the Qt5 legacy attribute."""
    enum_obj = getattr(owner, enum_name, None)
    if enum_obj is not None and hasattr(enum_obj, member_name):
        return getattr(enum_obj, member_name)
    if legacy_name is None:
        legacy_name = member_name
    return getattr(owner, legacy_name, default)


ALIGN_CENTER = _qt_value(Qt, "AlignmentFlag", "AlignCenter", default=0)
# Media status/error members used by QtVideoWidget's health check.
MEDIA_NOMEDIA = _qt_value(QMediaPlayer, "MediaStatus", "NoMedia", default=None) if HAS_QTMEDIA else None
MEDIA_INVALID = _qt_value(QMediaPlayer, "MediaStatus", "InvalidMedia", default=None) if HAS_QTMEDIA else None
MEDIA_NOERROR = _qt_value(QMediaPlayer, "Error", "NoError", default=None) if HAS_QTMEDIA else None
MEDIA_END = _qt_value(QMediaPlayer, "MediaStatus", "EndOfMedia", default=None) if HAS_QTMEDIA else None
MEDIA_STOPPED = _qt_value(QMediaPlayer, "PlaybackState", "StoppedState", default=None) if HAS_QTMEDIA else None
MEDIA_PLAYING = _qt_value(QMediaPlayer, "PlaybackState", "PlayingState", default=None) if HAS_QTMEDIA else None
ALIGN_LEFT = _qt_value(Qt, "AlignmentFlag", "AlignLeft", default=0)
ALIGN_TOP = _qt_value(Qt, "AlignmentFlag", "AlignTop", default=0)
KEEP_ASPECT = _qt_value(Qt, "AspectRatioMode", "KeepAspectRatio", default=1)
SMOOTH = _qt_value(Qt, "TransformationMode", "SmoothTransformation", default=1)
HORIZONTAL = _qt_value(Qt, "Orientation", "Horizontal", default=1)
USER_ROLE = _qt_value(Qt, "ItemDataRole", "UserRole", default=32)
WA_NATIVE_WINDOW = _qt_value(Qt, "WidgetAttribute", "WA_NativeWindow", default=100)
TEXT_SELECTABLE = _qt_value(Qt, "TextInteractionFlag", "TextSelectableByMouse", default=1)
LTR = _qt_value(Qt, "LayoutDirection", "LeftToRight", default=0)
RTL = _qt_value(Qt, "LayoutDirection", "RightToLeft", default=1)
POINTING_HAND = _qt_value(Qt, "CursorShape", "PointingHandCursor", default=None)

ViewMode_Icon = _qt_value(QtWidgets.QListView, "ViewMode", "IconMode")
Movement_Static = _qt_value(QtWidgets.QListView, "Movement", "Static")
Resize_Adjust = _qt_value(QtWidgets.QListView, "ResizeMode", "Adjust")
Selection_Extended = _qt_value(QtWidgets.QAbstractItemView, "SelectionMode", "ExtendedSelection")
Dialog_Accepted = _qt_value(QtWidgets.QDialog, "DialogCode", "Accepted")
OkButton = _qt_value(QtWidgets.QDialogButtonBox, "StandardButton", "Ok")
CancelButton = _qt_value(QtWidgets.QDialogButtonBox, "StandardButton", "Cancel")
ActionRole = _qt_value(QtWidgets.QDialogButtonBox, "ButtonRole", "ActionRole")
AcceptRole = _qt_value(QtWidgets.QMessageBox, "ButtonRole", "AcceptRole")
YesRole = _qt_value(QtWidgets.QMessageBox, "ButtonRole", "YesRole")
RejectRole = _qt_value(QtWidgets.QMessageBox, "ButtonRole", "RejectRole")
MsgBox_Yes = _qt_value(QtWidgets.QMessageBox, "StandardButton", "Yes")
MsgBox_No = _qt_value(QtWidgets.QMessageBox, "StandardButton", "No")


def _enum_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return int(getattr(value, "value", value))


def _is_dialog_accepted(result) -> bool:
    return _enum_int(result) == _enum_int(Dialog_Accepted)


# ---------------- early portable resource paths ----------------
SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
RUNTIME_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR


def _prepend_env_path(path: Path) -> None:
    try:
        if path.exists():
            os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(path))
                except Exception:
                    pass
    except Exception:
        pass


def configure_portable_runtime() -> None:
    """Expose bundled command-line tools and VLC runtime before optional imports."""
    for base in (RESOURCE_DIR / "bin", RUNTIME_DIR / "bin"):
        _prepend_env_path(base)
        vlc_dir = base / "vlc"
        _prepend_env_path(vlc_dir)
        libvlc = vlc_dir / "libvlc.dll"
        if libvlc.exists():
            os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(libvlc))
            os.environ.setdefault("PYTHON_VLC_MODULE_PATH", str(vlc_dir))
        plugins = vlc_dir / "plugins"
        if plugins.exists():
            os.environ.setdefault("VLC_PLUGIN_PATH", str(plugins))


configure_portable_runtime()

# ---------------- optional non-Qt dependencies ----------------
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:
    HAS_PIL = False

# Decompression-bomb guard: refuse absurdly large images (DoS protection).
if HAS_PIL:
    try:
        Image.MAX_IMAGE_PIXELS = min(int(Image.MAX_IMAGE_PIXELS or 89_478_485), 64_000_000)
    except Exception:
        Image.MAX_IMAGE_PIXELS = 64_000_000

try:
    import pymupdf  # PyMuPDF (new import name; "import fitz" is deprecated)
    HAS_FITZ = True
except Exception:
    try:
        import fitz as pymupdf  # very old PyMuPDF
        HAS_FITZ = True
    except Exception:
        HAS_FITZ = False

try:
    import rarfile
    HAS_RAR = True
except Exception:
    HAS_RAR = False

try:
    import py7zr
    HAS_7Z = True
except Exception:
    HAS_7Z = False

try:
    import vlc
    VLC_AVAILABLE = True
except Exception:
    VLC_AVAILABLE = False

# ---------------- paths & constants ----------------
ASSETS_DIR = RESOURCE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
APP_ICON = ASSETS_DIR / "icon.png"
APP_FONT = ASSETS_DIR / "Vazirmatn-Regular.ttf"

# Portable layout: config/cache/category sets are written next to the source file
# during development and next to the executable after PyInstaller build.
APP_DIR = RUNTIME_DIR / "user_data"
try:
    APP_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Read-only install location (e.g. Program Files): instead of crashing,
    # keep the portable data in a writable per-user folder.
    _fb_base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".filesorterviewer"))
    APP_DIR = _fb_base / "SortView" / "user_data"
    APP_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = APP_DIR / "app.log"
THUMB_CACHE = APP_DIR / "thumbs"
THUMB_CACHE.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = APP_DIR / "config.json"
CATEGORY_SETS_DIR = APP_DIR / "category_sets"
CATEGORY_SETS_DIR.mkdir(parents=True, exist_ok=True)

# Startup language: the saved user choice (config.json "language") wins,
# otherwise the OS display language is auto-detected. Switchable in the header.
app_i18n.load_saved_language(CONFIG_FILE)


def log_exception(context: str, exc: Optional[BaseException] = None) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}\n")
            if exc is not None:
                f.write(f"{type(exc).__name__}: {exc}\n")
            f.write(traceback.format_exc())
    except Exception:
        pass


def _global_excepthook(exc_type, exc, tb):
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] UNHANDLED EXCEPTION\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except Exception:
        pass
    try:
        sys.__excepthook__(exc_type, exc, tb)
    except Exception:
        pass


sys.excepthook = _global_excepthook

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif", ".jxl"}
ANIM_EXTS = {".gif"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".mpeg", ".mpg", ".m4v", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus", ".m4a", ".wma"}
DOC_EXTS = {".pdf", ".txt", ".md", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".epub"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
CODE_EXTS = {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".cpp", ".c", ".h", ".go", ".php", ".rb", ".java", ".rs"}

DEFAULT_THUMB = 168
HIGH_PREVIEW_MULT = 3
SAFE_MAX_IMAGE_DIM = 2400
# Archive-bomb guard: never read more than this from a single archive entry
# while hunting for a preview image.
MAX_ARCHIVE_IMAGE_BYTES = 64 * 1024 * 1024
CPU_COUNT = os.cpu_count() or 4
THUMB_BATCH_SIZE = max(8, min(32, CPU_COUNT * 2))
THUMB_MAX_WORKERS = max(4, min(16, CPU_COUNT))
THUMB_MAX_INFLIGHT = THUMB_MAX_WORKERS * 3
VIDEO_THUMB_PARALLEL = max(2, min(8, max(2, CPU_COUNT // 2)))
VIDEO_THUMB_SEMAPHORE = threading.BoundedSemaphore(VIDEO_THUMB_PARALLEL)
TYPE_CARD_MEM = {}
TRANSFER_CHUNK_SIZE = 2 * 1024 * 1024

EXT_ICON = {
    ".mp4": "video", ".mkv": "video", ".avi": "video", ".mov": "video", ".webm": "video", ".wmv": "video", ".flv": "video", ".mpeg": "video", ".mpg": "video", ".m4v": "video",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".aac": "audio", ".ogg": "audio", ".opus": "audio", ".m4a": "audio",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".bmp": "image", ".webp": "image", ".tiff": "image", ".gif": "image",
    ".zip": "zip", ".rar": "zip", ".7z": "zip", ".tar": "zip", ".gz": "zip",
    ".pdf": "pdf", ".txt": "document", ".md": "markdown", ".doc": "word", ".docx": "word", ".xls": "table", ".xlsx": "table", ".csv": "table", ".ppt": "powerpoint", ".pptx": "powerpoint", ".epub": "epub",
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".html": "html", ".htm": "html", ".css": "css", ".json": "json", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml", ".cpp": "cpp", ".c": "c", ".h": "c", ".go": "go", ".php": "php", ".rb": "ruby", ".java": "java", ".rs": "rust", ".log": "log",
    ".exe": "exe", ".msi": "exe", ".bat": "console", ".cmd": "console", ".ps1": "console", ".sh": "console",
    ".srt": "subtitles", ".ass": "subtitles", ".ssa": "subtitles", ".vtt": "subtitles", ".sub": "subtitles", ".idx": "subtitles",
}

GROUP_STYLE = {
    "video": ("#5b7cf5", "#33247e", "VIDEO"),
    "audio": ("#2dd4bf", "#0f766e", "AUDIO"),
    "image": ("#38bdf8", "#1e3a8a", "IMAGE"),
    "archive": ("#fbbf24", "#92400e", "ARCHIVE"),
    "doc": ("#fb7185", "#9f1239", "DOC"),
    "sub": ("#e879a9", "#9d2457", "SUB"),
    "code": ("#a3e635", "#3f6212", "CODE"),
    "exe": ("#94a3b8", "#334155", "APP"),
    "other": ("#8b98ad", "#25334a", "FILE"),
}

# Six visually distinct themes, ordered light -> dark for the picker dropdown.
# "dim" was removed in 1.7.0: its colours were nearly identical to Dark
# (ΔE < 10 on background and panel) and it only differed by its blue accent.
# danger_bg is the solid fill used on DangerBtn:hover — it must stay dark
# enough for WHITE text (>= 4.5:1), which the text-colour "danger" token
# alone can never guarantee on its own.
THEMES = {
    "light": {
        "label": "Light", "bg": "#f3f5f9", "panel": "#ffffff", "panel2": "#f6f8fb", "card": "#ffffff",
        "border": "#c6cfdb", "hover": "#e8edf4", "sel": "#d3deee", "text": "#1c2430", "muted": "#4f5965",
        "accent": "#3d5af1", "accent2": "#6a5cff", "danger": "#dc2626", "danger_bg": "#b91c1c", "preview_bg": "#e7ebf2",
    },
    "paper": {
        "label": "Paper", "bg": "#f2ebdc", "panel": "#fbf7ec", "panel2": "#f6f0e1", "card": "#fffdf6",
        "border": "#cdbf9f", "hover": "#ebe2cc", "sel": "#e2d3b0", "text": "#2f2819", "muted": "#5a503c",
        "accent": "#b4530a", "accent2": "#8f4108", "danger": "#b91c1c", "danger_bg": "#991b1b", "preview_bg": "#e8dfc9",
    },
    "graphite": {
        "label": "Graphite", "bg": "#24272d", "panel": "#2d3138", "panel2": "#343941", "card": "#353a42",
        "border": "#4b515c", "hover": "#3a4049", "sel": "#34494e", "text": "#eceef1", "muted": "#aab0ba",
        "accent": "#0b7f81", "accent2": "#096669", "danger": "#ff6b66", "danger_bg": "#dc2626", "preview_bg": "#1b1d22",
    },
    "dark": {
        "label": "Dark", "bg": "#0c111a", "panel": "#111927", "panel2": "#131b29", "card": "#141d2c",
        "border": "#34455f", "hover": "#182338", "sel": "#22344f", "text": "#e7edf6", "muted": "#93a1b5",
        "accent": "#3d5af1", "accent2": "#6a5cff", "danger": "#ef4444", "danger_bg": "#dc2626", "preview_bg": "#070a10",
    },
    "forest": {
        "label": "Forest", "bg": "#0e1612", "panel": "#142019", "panel2": "#192720", "card": "#1a2921",
        "border": "#2f4538", "hover": "#1e3027", "sel": "#244235", "text": "#e6efe9", "muted": "#95ab9f",
        "accent": "#19804f", "accent2": "#13683f", "danger": "#ff7468", "danger_bg": "#dc2626", "preview_bg": "#09100c",
    },
    "amoled": {
        "label": "AMOLED", "bg": "#000000", "panel": "#0d0d12", "panel2": "#111117", "card": "#13131a",
        "border": "#2b2b38", "hover": "#1a1a24", "sel": "#23233a", "text": "#f2f2f5", "muted": "#9a9aa8",
        "accent": "#6a5af0", "accent2": "#5a49e0", "danger": "#ff5c7a", "danger_bg": "#e11d48", "preview_bg": "#000000",
    },
}


def theme_color_icon(theme_key: str, size: int = 18) -> "QtGui.QIcon":
    """Two-colour circle for the theme picker dropdown.

    Left half = theme background, right half = accent colour, with a thin
    border ring, so the user sees the palette before choosing it.
    Rendered at 2x device pixels for crisp edges on scaled displays.
    """
    c = THEMES.get(theme_key, {})
    try:
        # Qt6 (PyQt6) scopes every enum, PyQt5/PySide6 legacy access differs —
        # resolve through the same _qt_value helper the rest of the file uses.
        TRANSPARENT = _qt_value(Qt, "GlobalColor", "transparent")
        NO_PEN = _qt_value(Qt, "PenStyle", "NoPen")
        NO_BRUSH = _qt_value(Qt, "BrushStyle", "NoBrush")
        d = size * 2
        pm = QPixmap(d, d)
        pm.fill(TRANSPARENT)
        p = QtGui.QPainter(pm)
        hint = getattr(QtGui.QPainter, "RenderHint", None)
        aa = hint.Antialiasing if hint is not None else getattr(QtGui.QPainter, "Antialiasing", None)
        if aa is not None:
            p.setRenderHint(aa)
        rect = QtCore.QRectF(2.0, 2.0, d - 4.0, d - 4.0)
        p.setPen(NO_PEN)
        p.setClipRect(QtCore.QRectF(rect.left(), rect.top(), rect.width() / 2.0, rect.height()))
        p.setBrush(QtGui.QColor(c.get("bg", "#222222")))
        p.drawEllipse(rect)
        p.setClipRect(QtCore.QRectF(rect.left() + rect.width() / 2.0, rect.top(), rect.width() / 2.0, rect.height()))
        p.setBrush(QtGui.QColor(c.get("accent", "#888888")))
        p.drawEllipse(rect)
        p.setClipping(False)
        p.setPen(QtGui.QPen(QtGui.QColor(c.get("border", "#666666")), 2.0))
        p.setBrush(NO_BRUSH)
        p.drawEllipse(rect.adjusted(1.0, 1.0, -1.0, -1.0))
        p.end()
        pm.setDevicePixelRatio(2.0)
        return QIcon(pm)
    except Exception:
        return QIcon()


class HeaderCombo(QtWidgets.QComboBox):
    """QComboBox that always paints a theme-coloured drop arrow.

    With `QComboBox::drop-down { border: none }` Qt stops painting the arrow
    entirely (the combo looked like a plain text field). Stylesheets cannot
    render a triangle for ::down-arrow either — the CSS border-trick paints
    a solid rectangle because Qt draws borders per side, and image files
    would not survive the frozen exe without qrc resources. So the arrow is
    painted here directly, in the theme's muted colour (set via the
    `arrow_color` property from apply_theme).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.arrow_color = "#93a1b5"

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            try:
                no_pen = Qt.PenStyle.NoPen
            except AttributeError:
                no_pen = Qt.NoPen
            try:
                rtl = QtCore.Qt.LayoutDirection.RightToLeft
            except AttributeError:
                rtl = QtCore.Qt.RightToLeft
            p = QtGui.QPainter(self)
            hint = getattr(QtGui.QPainter, "RenderHint", None)
            aa = hint.Antialiasing if hint is not None else getattr(QtGui.QPainter, "Antialiasing", None)
            if aa is not None:
                p.setRenderHint(aa)
            r = self.rect()
            drop_w = 24  # keep in sync with QComboBox::drop-down width in build_qss
            x = r.width() - drop_w / 2.0 if self.layoutDirection() != rtl else drop_w / 2.0
            y = r.height() / 2.0
            p.setPen(no_pen)
            p.setBrush(QtGui.QColor(getattr(self, "arrow_color", "#93a1b5")))
            p.drawPolygon(QtCore.QPointF(x - 5.0, y - 3.0),
                          QtCore.QPointF(x + 5.0, y - 3.0),
                          QtCore.QPointF(x, y + 3.5))
            p.end()
        except Exception:
            pass


def build_qss(theme_name: str) -> str:
    c = THEMES.get(theme_name, THEMES["dark"])
    return f"""
* {{ outline: none; }}
QWidget {{ background: {c['bg']}; color: {c['text']}; font-size: 13px; }}
QMainWindow {{ background: {c['bg']}; }}
QDialog {{ background: {c['panel']}; }}
QFrame#Panel {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QFrame#PreviewPanel {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 16px; }}
QLabel#Title {{ font-size: 18px; font-weight: 800; background: transparent; }}
QLabel#Muted {{ color: {c['muted']}; background: transparent; }}
QLabel#FieldLabel {{ color: {c['muted']}; background: transparent; font-weight: 700; }}
QLabel#HeaderIcon {{ background: transparent; }}
QFrame#ChipSeparator {{ background: {c['border']}; border: none; }}
QLabel#StatusLabel {{ color: {c['muted']}; background: transparent; padding: 4px; }}
QLabel#Preview {{ background: {c['preview_bg']}; color: {c['muted']}; border: 1px solid {c['border']}; border-radius: 14px; }}
QPushButton {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 8px 12px; }}
QPushButton:hover {{ background: {c['hover']}; border-color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['sel']}; }}
QPushButton#PrimaryBtn {{ background: {c['accent']}; color: white; border: none; font-weight: 700; }}
QPushButton#PrimaryBtn:hover {{ background: {c['accent2']}; }}
QPushButton#DangerBtn {{ background: transparent; color: {c['danger']}; border-color: {c['danger']}; }}
QPushButton#DangerBtn:hover {{ background: {c['danger_bg']}; color: white; border-color: {c['danger_bg']}; }}
QPushButton#SegBtn {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 5px 12px; color: {c['muted']}; font-weight: 600; }}
QPushButton#SegBtn:hover {{ background: {c['hover']}; color: {c['text']}; border-color: transparent; }}
QPushButton#SegBtn:checked {{ background: {c['accent']}; color: #ffffff; border-color: {c['accent']}; }}
/* Keyboard focus must be visible: outline:none kills the system ring, so
   buttons get an accent border instead; accent-filled buttons get a text-
   coloured one (an accent border on an accent fill would be invisible). */
QPushButton:focus {{ border-color: {c['accent']}; }}
QPushButton#PrimaryBtn:focus, QPushButton:checked:focus {{ border-color: {c['text']}; }}
QPushButton#PrimaryBtn:disabled {{ background: {c['hover']}; color: {c['muted']}; border: 1px solid {c['border']}; }}
QPushButton#DangerBtn:disabled {{ background: transparent; color: {c['muted']}; border-color: {c['border']}; }}
QPushButton:disabled {{ background: {c['panel']}; color: {c['muted']}; border-color: {c['border']}; }}
QLineEdit, QComboBox {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 7px 9px; selection-background-color: {c['accent']}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {c['accent']}; }}
QLineEdit:disabled, QComboBox:disabled {{ background: {c['hover']}; color: {c['muted']}; border-color: {c['border']}; }}
QListWidget {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 14px; padding: 6px; }}
QListWidget::item {{ border-radius: 10px; padding: 5px; margin: 3px; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
QListWidget::item:selected {{ background: {c['sel']}; color: {c['text']}; border: 1px solid {c['accent']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QProgressBar {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 8px; text-align: center; height: 12px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 7px; }}
QSlider::groove:horizontal {{ height: 6px; background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {c['accent']}; border: none; width: 16px; margin: -5px 0; border-radius: 8px; }}
QSlider::handle:horizontal:hover {{ background: {c['accent2']}; }}
/* Slim themed scrollbars — the system ones stayed bright/light inside dark
   panels and clashed with every theme. */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 32px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['muted']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
QStatusBar {{ background: {c['panel']}; border-top: 1px solid {c['border']}; }}
QStatusBar QLabel {{ background: transparent; color: {c['muted']}; }}
QSplitter::handle {{ background: {c['bg']}; }}
QToolTip {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; border-radius: 6px; }}
QFrame#HeaderTools {{ background: {c['panel2']}; border: 1px solid {c['border']}; border-radius: 12px; }}
QFrame#HeaderTools QLabel {{ background: transparent; color: {c['muted']}; font-weight: 700; }}
QComboBox QAbstractItemView {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; outline: none; selection-background-color: {c['sel']}; selection-color: {c['text']}; }}
QComboBox QAbstractItemView::item {{ padding: 6px 16px; margin: 2px 4px; }}
QComboBox QAbstractItemView::item:selected {{ background: {c['sel']}; color: {c['text']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
/* The arrow itself is painted by HeaderCombo.paintEvent (see class docstring):
   Qt draws no arrow when drop-down has no border, and no stylesheet trick
   produces a real triangle. */
QCheckBox {{ background: transparent; spacing: 8px; }}
QFrame#CheckCard {{ background: {c['panel2']}; border: 1px solid {c['accent']}; border-radius: 12px; }}
QFrame#CheckCard QLabel {{ background: transparent; border: none; }}
QLabel#CheckHint {{ color: {c['muted']}; }}
QCheckBox#BigCheck {{ background: transparent; spacing: 10px; font-weight: 700; color: {c['text']}; }}
QCheckBox#BigCheck::indicator {{ width: 20px; height: 20px; border: 2px solid {c['accent']}; border-radius: 6px; background: {c['bg']}; }}
QCheckBox#BigCheck::indicator:hover {{ background: {c['hover']}; }}
QCheckBox#BigCheck::indicator:checked {{ background: {c['accent']}; border-color: {c['accent2']}; }}
QMenu {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['sel']}; }}
QMessageBox {{ background: {c['panel']}; }}
QMessageBox QLabel {{ background: transparent; }}
QMessageBox QPushButton {{ min-width: 76px; }}
/* Dialogs, message boxes and input dialogs must not paint light label boxes:
   the generic QWidget rule gives every QLabel an opaque bg-coloured rectangle
   that stands out against the panel colour of the dialog itself. */
QLabel {{ background: transparent; }}
QDialog QLabel {{ background: transparent; }}
QInputDialog {{ background: {c['panel']}; }}
QInputDialog QLabel {{ background: transparent; }}
/* QSpinBox (used by the swap-categories dialog) otherwise falls back to the
   light system palette on Windows — a white field inside a dark dialog. */
QSpinBox {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 5px 7px; selection-background-color: {c['accent']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ background: {c['hover']}; border: none; width: 18px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {c['sel']}; }}
/* QInputDialog's chooser list is a plain QListView, not a QListWidget. */
QListView {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; outline: none; }}
QListView::item {{ border-radius: 8px; padding: 5px; margin: 2px; }}
QListView::item:hover {{ background: {c['hover']}; }}
QListView::item:selected {{ background: {c['sel']}; color: {c['text']}; border: 1px solid {c['accent']}; }}
/* Small check indicators follow the theme instead of the system palette. */
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {c['border']}; border-radius: 4px; background: {c['bg']}; }}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent2']}; }}
"""


def build_palette(theme_name: str) -> QtGui.QPalette:
    """A QPalette that matches the theme.

    A stylesheet never changes the QPalette, so with Fusion on Windows every
    widget/subcontrol the QSS does not explicitly cover (QSpinBox fields,
    disabled text, native popups, message-box details) still drew with the
    LIGHT system palette — white patches inside dark dialogs. Seeding the
    palette with the theme colours removes those mismatched areas app-wide.
    """
    c = THEMES.get(theme_name, THEMES["dark"])
    pal = QtGui.QPalette()
    text = QtGui.QColor(c["text"])
    muted = QtGui.QColor(c["muted"])
    disabled = QtGui.QColor(c["muted"])
    disabled.setAlpha(150)
    R = QtGui.QPalette.ColorRole
    G = QtGui.QPalette.ColorGroup
    pal.setColor(R.Window, QtGui.QColor(c["bg"]))
    pal.setColor(R.WindowText, text)
    pal.setColor(R.Base, QtGui.QColor(c["panel"]))
    pal.setColor(R.AlternateBase, QtGui.QColor(c["panel2"]))
    pal.setColor(R.ToolTipBase, QtGui.QColor(c["panel2"]))
    pal.setColor(R.ToolTipText, text)
    pal.setColor(R.Text, text)
    pal.setColor(R.Button, QtGui.QColor(c["panel2"]))
    pal.setColor(R.ButtonText, text)
    pal.setColor(R.PlaceholderText, muted)
    pal.setColor(R.Highlight, QtGui.QColor(c["accent"]))
    pal.setColor(R.HighlightedText, QtGui.QColor("#ffffff"))
    pal.setColor(R.Link, QtGui.QColor(c["accent2"]))
    for role in (R.WindowText, R.Text, R.ButtonText):
        pal.setColor(G.Disabled, role, disabled)
    pal.setColor(G.Disabled, R.Base, QtGui.QColor(c["panel2"]))
    return pal


def _apply_windows_titlebar(widget: QtWidgets.QWidget, dark: bool):
    """Colour the native Windows title bar to match the app theme.

    Windows decides title-bar colour from the SYSTEM theme, never from the Qt
    palette — so a dark-themed app got white title bars on every dialog.
    DWMWA_USE_IMMERSIVE_DARK_MODE (20; 19 on older builds) fixes that.
    """
    if sys.platform != "win32" or widget is None:
        return
    try:
        import ctypes
        import ctypes.wintypes
        hwnd = int(widget.winId())
        for attr in (20, 19):
            val = ctypes.c_int(1 if dark else 0)
            res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.wintypes.HWND(hwnd), ctypes.c_uint(attr),
                ctypes.byref(val), ctypes.sizeof(val))
            if res == 0:
                break
    except Exception:
        pass


def _apply_app_color_scheme(dark: bool):
    """Tell the platform theme that this app is dark/light (Qt >= 6.8).

    On Windows 10/11 the native title bar of EVERY window — including dialogs
    and message boxes created later — follows the application colour scheme,
    so a dark-themed app no longer gets white dialog title bars. Older Qt
    builds skip this gracefully (cosmetic-only degradation). Unlike an
    app-wide event filter, this has no teardown-time risk and needs no
    per-window bookkeeping.
    """
    try:
        sh = QtWidgets.QApplication.styleHints()
        cs = getattr(QtCore.Qt, "ColorScheme", None)
        if sh is not None and cs is not None and hasattr(sh, "setColorScheme"):
            sh.setColorScheme(cs.Dark if dark else cs.Light)
    except Exception:
        pass


# ---------------- utility helpers ----------------
def bundled_tool(name: str) -> Optional[str]:
    """Find a tool from bundled bin/, app folder bin/, or system PATH."""
    names = [name]
    if sys.platform == "win32" and not name.lower().endswith(".exe"):
        names.insert(0, name + ".exe")
    for base in (RESOURCE_DIR / "bin", RUNTIME_DIR / "bin"):
        for nm in names:
            fp = base / nm
            if fp.exists():
                return str(fp)
    return which(name) or (which(name + ".exe") if sys.platform == "win32" and not name.lower().endswith(".exe") else None)


def portable_vlc_dir() -> Optional[Path]:
    for base in (RESOURCE_DIR / "bin", RUNTIME_DIR / "bin"):
        d = base / "vlc"
        if (d / "libvlc.dll").exists():
            return d
    return None


def run_hidden_subprocess(cmd, **kwargs):
    """Run console tools without flashing terminal windows on Windows."""
    if sys.platform == "win32":
        try:
            flags = subprocess.CREATE_NO_WINDOW
            flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            kwargs.setdefault("creationflags", flags)
        except Exception:
            pass
        try:
            startupinfo = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
        except Exception:
            pass
    return subprocess.run(cmd, **kwargs)


def popen_hidden_subprocess(cmd, **kwargs):
    """Start console tools without a flashing console window on Windows."""
    if sys.platform == "win32":
        try:
            kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass
        try:
            startupinfo = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
        except Exception:
            pass
    return subprocess.Popen(cmd, **kwargs)


def ffmpeg_available() -> bool:
    return bundled_tool("ffmpeg") is not None


def extract_frame_with_ffmpeg(path: str, fraction=0.5, out_png: Optional[str] = None, timeout: int = 8) -> Optional[str]:
    """Extract one video frame quickly and silently.

    Thumbnail generation deliberately uses a single ffmpeg call and no
    separate ffprobe/duration pass — a second external process per file made
    folders full of videos feel very slow. A frame around 1 second is
    fast and good enough for sorting — but clips SHORTER than the seek point
    produce no frame at all, so on an empty result we retry with earlier seek
    positions (0.4s, then the very first frame). That is how very short clips
    (< 1 s) still get a real thumbnail.
    """
    if out_png is None:
        out_png = str(THUMB_CACHE / f"ffthumb_{int(time.time() * 1000)}.png")
    result = None
    attempt_files: List[str] = []
    try:
        ffmpeg = bundled_tool("ffmpeg")
        if ffmpeg is None:
            return None
        base_fp = Path(out_png)
        for idx, seek in enumerate(("1", "0.4", "0")):
            # A unique file per attempt: a failed attempt must never be
            # mistaken for a successfully written frame.
            attempt_out = str(base_fp.with_name(f"{base_fp.stem}_a{idx}{base_fp.suffix}"))
            attempt_files.append(attempt_out)
            # -ss before -i is much faster. scale keeps generated PNG small.
            cmd = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-threads", "1", "-ss", seek, "-noaccurate_seek", "-i", str(path),
                "-an", "-sn", "-dn", "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "5", attempt_out,
            ]
            try:
                with open(os.devnull, "wb") as dn:
                    run_hidden_subprocess(cmd, stdout=dn, stderr=dn, timeout=timeout)
            except Exception:
                pass
            fp = Path(attempt_out)
            if fp.exists() and fp.stat().st_size > 0:
                result = attempt_out
                break
    except Exception as e:
        log_exception("ffmpeg thumbnail extraction failed", e)
    finally:
        # Temp-file hygiene: every attempt file that is NOT the returned frame
        # is deleted here. Without this, failed attempts pile up in the system
        # TEMP folder next to the returned frame (found by the v1.9.2 review).
        for stale in attempt_files:
            if stale == result:
                continue
            try:
                if Path(stale).exists():
                    Path(stale).unlink()
            except Exception:
                pass
    return result


def thumb_cache_key(path: str, size: int) -> str:
    try:
        st = Path(path).stat()
        key_src = f"{Path(path).resolve()}|{st.st_mtime_ns}|{st.st_size}|{size}|qt6-v4"
    except Exception:
        key_src = f"{path}|{size}|qt6-v4"
    # usedforsecurity=False: the SHA1 is only a cache key for thumbnails,
    # never a security primitive (also silences static analyzers like bandit).
    return hashlib.sha1(key_src.encode("utf-8"), usedforsecurity=False).hexdigest()


def cached_thumbnail_bytes(path: str, size: int) -> Optional[bytes]:
    try:
        fp = THUMB_CACHE / (thumb_cache_key(path, size) + ".png")
        if fp.exists():
            data = fp.read_bytes()
            return data if data else None
    except Exception:
        pass
    return None


def _write_cache_safely(cache_fp: Path, data: bytes) -> None:
    try:
        tmp = cache_fp.with_suffix(cache_fp.suffix + f".tmp{os.getpid()}{threading.get_ident()}")
        tmp.write_bytes(data)
        os.replace(str(tmp), str(cache_fp))
    except Exception:
        try:
            if "tmp" in locals() and tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _png_from_pil_image(im, max_size: int) -> bytes:
    if im.mode not in ("RGBA", "RGB"):
        im = im.convert("RGBA")
    im.thumbnail((max_size * 2, max_size * 2), Image.LANCZOS)
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


def group_for_extension(ext: str) -> str:
    ext = ext.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS or ext in ANIM_EXTS:
        return "image"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in SUBTITLE_EXTS:
        return "sub"
    if ext in CODE_EXTS:
        return "code"
    if ext in {".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh"}:
        return "exe"
    if ext in DOC_EXTS:
        return "doc"
    return "other"


def _is_mpeg_ts_file(p) -> bool:
    """True if a `.ts` file really is an MPEG Transport Stream.

    The `.ts` extension is ambiguous: it is both the MPEG-TS video container
    and TypeScript source code, and it sits in VIDEO_EXTS *and* CODE_EXTS.
    Every MPEG-TS packet starts with the sync byte 0x47 and packets are
    188 bytes, so the first byte plus the sync byte of the second packet
    (offset 188) is a strong signal. Anything else — including text that
    merely happens to start with the letter 'G' (0x47) — is treated as code.
    """
    try:
        with open(p, "rb") as fh:
            head = fh.read(189)
    except OSError:
        return False
    if len(head) == 0 or head[0] != 0x47:
        return False
    if len(head) >= 189 and head[188] != 0x47:
        return False
    return True


def _plays_as_video(path) -> bool:
    """Extension says video AND, for the ambiguous .ts, content agrees."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in VIDEO_EXTS:
        return False
    if ext == ".ts":
        return _is_mpeg_ts_file(p)
    return True


def _asset_icon_pil(ext: str, side: int):
    if not HAS_PIL:
        return None
    icon_name = EXT_ICON.get(ext.lower())
    if not icon_name:
        icon_name = {"video": "video", "audio": "audio", "image": "image", "archive": "zip", "doc": "document", "sub": "subtitles", "code": "console", "exe": "exe", "other": "document"}.get(group_for_extension(ext), "document")
    fp = ICONS_DIR / f"{icon_name}.png"
    if not fp.exists():
        return None
    try:
        im = Image.open(str(fp)).convert("RGBA")
        im.thumbnail((side, side), Image.LANCZOS)
        return im
    except Exception:
        return None


def _font(size: int, bold: bool = False):
    if not HAS_PIL:
        return None
    candidates = []
    if APP_FONT.exists():
        candidates.append(str(APP_FONT))
    candidates += ["arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_type_card_bytes(path: str, size: int) -> Optional[bytes]:
    """File-type artwork: self-contained document-style icon, gradient card fallback.

    Known extensions map to a real document-style icon from assets/icons/
    (white page + colored label, original AI-generated artwork). Anything
    unmapped falls back to the gradient card that spells out the extension.
    """
    if not HAS_PIL:
        return None
    try:
        p = Path(path)
        ext = p.suffix.lower()
        if ext in EXT_ICON:
            icon = _asset_icon_pil(ext, max(128, int(size * 2)))
            if icon is not None:
                bio = io.BytesIO()
                icon.save(bio, format="PNG")
                return bio.getvalue()
        group = group_for_extension(ext)
        c1, c2, label = GROUP_STYLE.get(group, GROUP_STYLE["other"])
        w = h = max(128, int(size * 2))
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = max(16, w // 10)
        # vertical gradient
        def hexrgb(x):
            x = x.lstrip("#")
            return tuple(int(x[i:i+2], 16) for i in (0, 2, 4))
        a = hexrgb(c1); b = hexrgb(c2)
        for y in range(h):
            t = y / max(1, h - 1)
            col = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3)) + (255,)
            draw.line([(0, y), (w, y)], fill=col)
        # soft overlay and border
        draw.rounded_rectangle([2, 2, w - 3, h - 3], radius=r, outline=(255, 255, 255, 68), width=max(2, w // 80))
        draw.rounded_rectangle([w * 0.08, h * 0.08, w * 0.92, h * 0.92], radius=r, fill=(255, 255, 255, 18))
        icon = _asset_icon_pil(ext, int(w * 0.43))
        if icon:
            x = (w - icon.width) // 2
            y = int(h * 0.19)
            img.alpha_composite(icon, (x, y))
        ext_text = (ext[1:] if ext else label).upper()[:8]
        font_big = _font(max(18, w // 8), bold=True)
        font_small = _font(max(12, w // 15))
        bbox = draw.textbbox((0, 0), ext_text, font=font_big)
        tx = (w - (bbox[2] - bbox[0])) // 2
        ty = int(h * 0.64)
        draw.text((tx + 2, ty + 2), ext_text, fill=(0, 0, 0, 90), font=font_big)
        draw.text((tx, ty), ext_text, fill=(255, 255, 255, 245), font=font_big)
        bbox2 = draw.textbbox((0, 0), label, font=font_small)
        draw.text(((w - (bbox2[2] - bbox2[0])) // 2, int(h * 0.82)), label, fill=(255, 255, 255, 180), font=font_small)
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        return bio.getvalue()
    except Exception:
        return None


def _first_image_from_zip(path: Path, size: int) -> Optional[bytes]:
    with zipfile.ZipFile(str(path), "r") as z:
        for info in z.infolist():
            if Path(info.filename).suffix.lower() in IMAGE_EXTS:
                if info.file_size > MAX_ARCHIVE_IMAGE_BYTES:
                    continue  # archive-bomb guard: skip absurdly large entries
                try:
                    with z.open(info) as fh:
                        with Image.open(fh) as im:
                            return _png_from_pil_image(im, size)
                except Exception:
                    continue
    return None


def _first_image_from_rar(path: Path, size: int) -> Optional[bytes]:
    if not HAS_RAR:
        return None
    with rarfile.RarFile(str(path)) as rf:
        for info in rf.infolist():
            if Path(info.filename).suffix.lower() in IMAGE_EXTS:
                if int(getattr(info, "file_size", 0) or 0) > MAX_ARCHIVE_IMAGE_BYTES:
                    continue  # archive-bomb guard
                try:
                    with rf.open(info) as fh:
                        with Image.open(fh) as im:
                            return _png_from_pil_image(im, size)
                except Exception:
                    continue
    return None


def _first_image_from_7z(path: Path, size: int) -> Optional[bytes]:
    if not HAS_7Z:
        return None
    try:
        with py7zr.SevenZipFile(str(path), mode="r") as archive:
            targets: List[str] = []
            for entry in archive.list():
                name = getattr(entry, "filename", None)
                if not name or Path(name).suffix.lower() not in IMAGE_EXTS:
                    continue
                if int(getattr(entry, "uncompressed", 0) or 0) > MAX_ARCHIVE_IMAGE_BYTES:
                    continue  # archive-bomb guard
                targets.append(name)
                if len(targets) >= 20:
                    break
            if not targets:
                return None
            archive.reset()  # rewind after list() before extracting
            with tempfile.TemporaryDirectory(prefix="sv7z-") as td:
                # py7zr 1.x removed the old in-memory read() API; extract the
                # small image entries to a temp dir instead (they passed the
                # archive-bomb size guard above, so this stays bounded).
                archive.extract(path=td, targets=targets)
                base = Path(td).resolve()
                for name in targets:
                    fp = (base / name).resolve()
                    # Containment guard: never read anything outside td,
                    # whatever the archive claims its entry names are.
                    if not fp.is_relative_to(base) or not fp.is_file():
                        continue
                    try:
                        with Image.open(fp) as im:
                            return _png_from_pil_image(im, size)
                    except Exception:
                        continue
    except Exception as e:
        log_exception("py7zr archive thumbnail failed", e)
    return None


def _first_image_from_tar(path: Path, size: int) -> Optional[bytes]:
    """Archive thumbnail for .tar/.tar.gz/.tgz via the stdlib tarfile module.

    Replaces the old bundled-7za fallback for the tar family (since v1.10.3
    the portable build ships no 7za.exe). Streaming iteration stops at the
    first image entry, so a huge tar never needs a full listing up front.
    """
    if not HAS_PIL:
        return None
    try:
        with tarfile.open(str(path), "r:*") as tf:
            for member in tf:
                if not member.isfile():
                    continue
                if Path(member.name).suffix.lower() not in IMAGE_EXTS:
                    continue
                if member.size > MAX_ARCHIVE_IMAGE_BYTES:
                    continue  # archive-bomb guard
                try:
                    fh = tf.extractfile(member)
                    if fh is None:
                        continue
                    with Image.open(fh) as im:
                        return _png_from_pil_image(im, size)
                except Exception:
                    continue
    except Exception as e:
        log_exception("tar archive thumbnail failed", e)
    return None




def sevenzip_tool() -> Optional[str]:
    return bundled_tool("7za") or bundled_tool("7z")


def _first_image_from_7zip_cli(path: Path, size: int) -> Optional[bytes]:
    """Archive thumbnail fallback through a system 7-Zip (7z.exe), if present.

    Since v1.10.3 the portable build ships no 7za.exe: py7zr (.7z), stdlib
    zipfile (.zip) and tarfile (.tar/.tar.gz) cover the everyday formats,
    so this only ever fires on dev machines that have 7-Zip installed.
    RAR is NOT supported (proprietary codec) and falls back to a type card.
    """
    if not HAS_PIL:
        return None
    tool = sevenzip_tool()
    if not tool:
        return None
    try:
        listing = run_hidden_subprocess(
            # -spd: entry names containing * or ? are literal names, not
            # wildcards (7-Zip would otherwise try to glob them).
            [tool, "l", "-slt", "-spd", "--", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        if listing.returncode != 0 or not listing.stdout:
            return None
        text = listing.stdout.decode("utf-8", errors="replace")
        # Parse Path/Size pairs ("Size = " follows its "Path = " line in -slt
        # output) so huge entries can be skipped without extracting them.
        names = []
        current = None
        for line in text.splitlines():
            if line.startswith("Path = "):
                current = {"name": line[7:].strip(), "size": 0}
                if current["name"] and Path(current["name"]).suffix.lower() in IMAGE_EXTS:
                    names.append(current)
                else:
                    current = None
            elif current is not None and line.startswith("Size = "):
                try:
                    current["size"] = int(line[7:].strip().replace(" ", ""))
                except ValueError:
                    current["size"] = 0
        for entry in names[:20]:
            name, esize = entry["name"], entry["size"]
            if esize > MAX_ARCHIVE_IMAGE_BYTES:
                continue  # archive-bomb guard
            try:
                out = run_hidden_subprocess(
                    [tool, "e", "-so", "-spd", "--", str(path), name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                if out.returncode == 0 and out.stdout:
                    if len(out.stdout) > MAX_ARCHIVE_IMAGE_BYTES:
                        continue  # archive-bomb guard
                    with Image.open(io.BytesIO(out.stdout)) as im:
                        return _png_from_pil_image(im, size)
            except Exception:
                continue
    except Exception as e:
        log_exception("7zip archive thumbnail failed", e)
    return None


def generate_thumbnail_bytes(path: str, size: int, allow_expensive: bool = True) -> Optional[bytes]:
    """Generate PNG bytes for a file thumbnail/card. Safe for worker threads."""
    p = Path(path)
    ext = p.suffix.lower()
    if not allow_expensive and ext not in IMAGE_EXTS and ext not in ANIM_EXTS:
        mem_key = (ext or group_for_extension(ext), int(size))
        data = TYPE_CARD_MEM.get(mem_key)
        if data is None:
            data = generate_type_card_bytes("file" + ext, size) or b""
            TYPE_CARD_MEM[mem_key] = data
        return data or None
    key = thumb_cache_key(path, size)
    cache_fp = THUMB_CACHE / (key + ".png")
    if cache_fp.exists():
        try:
            data = cache_fp.read_bytes()
            if data:
                return data
        except Exception:
            pass

    data = None
    cache_ok = True
    if ext in IMAGE_EXTS and HAS_PIL:
        try:
            with Image.open(str(p)) as im:
                data = _png_from_pil_image(im, size)
        except Exception:
            data = None

    if data is None and ext in ANIM_EXTS and HAS_PIL:
        try:
            with Image.open(str(p)) as im:
                im.seek(0)
                data = _png_from_pil_image(im, size)
        except Exception:
            data = None

    if allow_expensive and data is None and _plays_as_video(p) and ffmpeg_available():
        tmp_name = None
        res = None
        acquired = VIDEO_THUMB_SEMAPHORE.acquire(timeout=15)
        if acquired:
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                tmp_name = tmp.name
                tmp.close()
                res = extract_frame_with_ffmpeg(path, fraction=0.5, out_png=tmp_name, timeout=10)
                if res and Path(res).exists():
                    raw = Path(res).read_bytes()
                    if HAS_PIL:
                        try:
                            with Image.open(io.BytesIO(raw)) as im:
                                data = _png_from_pil_image(im, size)
                        except Exception:
                            data = raw
                    else:
                        data = raw
            except Exception:
                data = None
            finally:
                # Delete BOTH temp files: the empty NamedTemporaryFile
                # placeholder (tmp_name) and the frame file that
                # extract_frame_with_ffmpeg() returned (res). res used to be
                # leaked — one leftover PNG per video thumbnail in the system
                # TEMP folder (bug found by the v1.9.2 review).
                for stale in (tmp_name, res):
                    try:
                        if stale and Path(stale).exists():
                            Path(stale).unlink()
                    except Exception:
                        pass
                try:
                    VIDEO_THUMB_SEMAPHORE.release()
                except Exception:
                    pass
        else:
            # Too many video thumbnails are already being generated. Show a card
            # for now, but do not cache it as the real video thumbnail.
            cache_ok = False

    if allow_expensive and data is None and ext == ".pdf" and HAS_FITZ:
        doc = None
        try:
            doc = pymupdf.open(str(p))
            if doc.page_count > 0:
                page = doc.load_page(0)
                zoom = max(1.0, min(3.0, size / 100.0))
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                data = pix.tobytes("png")
        except Exception:
            data = None
        finally:
            try:
                if doc is not None:
                    doc.close()
            except Exception:
                pass

    if allow_expensive and data is None and ext in ARCHIVE_EXTS and HAS_PIL:
        try:
            if ext == ".zip":
                data = _first_image_from_zip(p, size)
            elif ext == ".rar":
                data = _first_image_from_rar(p, size)
            elif ext == ".7z":
                data = _first_image_from_7z(p, size)
            elif ext in (".tar", ".gz"):
                data = _first_image_from_tar(p, size)
            if data is None:
                data = _first_image_from_7zip_cli(p, size)
        except Exception as e:
            log_exception("archive thumbnail failed", e)
            data = None

    # Always return a nice card if no real preview exists.
    if data is None:
        data = generate_type_card_bytes(path, size)

    if data and cache_ok:
        _write_cache_safely(cache_fp, data)
    return data


def parse_extension_filter(text: str) -> List[str]:
    """Parse extension filters.

    Accepts common forms: ".jpg,.png", "jpg png", "*.jpg;*.mp4".
    A full wildcard ("*" or "*.*") means no filtering.
    """
    result = []
    for token in re.split(r"[,;\s]+", text.strip().lower()):
        token = token.strip()
        if not token:
            continue
        if token in {"*", ".*", "*.*"}:
            return []
        if token.startswith("*."):
            token = token[1:]  # "*.jpg" -> ".jpg"
        elif token.startswith("*") and "." in token:
            token = token[token.rfind("."):]
        if token.startswith(".") and "*" in token:
            token = token.replace("*", "")
        if not token or token == ".":
            continue
        if not token.startswith("."):
            token = "." + token
        if token not in result:
            result.append(token)
    return result


def natural_key(text: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def sort_key_for_path(path: Path, mode: str):
    if mode in {"Type", "نوع"}:
        return (path.suffix.lower(), natural_key(path.name))
    return natural_key(path.name)


def normalize_categories(categories) -> List[dict]:
    cleaned = []
    if not isinstance(categories, list):
        return cleaned
    seen = set()
    for item in categories:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip() or "Untitled"
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        norm_path = str(Path(path).expanduser())
        key = (name.lower(), norm_path)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"name": name, "path": norm_path})
    return cleaned


def safe_filename_stem(stem: str) -> str:
    cleaned = "".join(ch for ch in stem if ch.isalnum() or ch in " _-.").strip()
    return cleaned or str(int(time.time()))


def unique_destination(base_path: Path, reserved: Optional[set] = None) -> Path:
    reserved = reserved or set()
    parent = base_path.parent
    stem = base_path.stem
    suffix = base_path.suffix
    candidate = base_path
    i = 1
    while candidate.exists() or str(candidate) in reserved:
        candidate = parent / f"{stem} ({i}){suffix}"
        i += 1
    return candidate


def same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return os.path.abspath(str(a)) == os.path.abspath(str(b))


def force_unlink(p: Path) -> None:
    """Delete p, clearing the Windows read-only attribute if necessary.

    Plain Path.unlink() raises PermissionError on Windows for files with the
    read-only attribute set, which used to make moving such files fail and
    even leave stray half-copied files behind. The attribute is cleared and
    the delete retried; every other error propagates to the caller as before.
    """
    try:
        p.unlink()
    except PermissionError:
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass
        p.unlink()


def file_size_text(path: Path) -> str:
    try:
        n = path.stat().st_size
    except Exception:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}" if u != "B" else f"{int(f)} B"
        f /= 1024
    return ""


# ---------------- worker signals/classes ----------------
class ThumbSignals(QtCore.QObject):
    finished = Signal(int, str, bytes, int)


class ScannerThread(QtCore.QThread):
    file_found = Signal(int, str)
    scan_done = Signal(int)
    scan_error = Signal(int, str)

    def __init__(self, scan_id: int, folder: str, recursive: bool):
        super().__init__()
        self.scan_id = scan_id
        self.folder = folder
        self.recursive = bool(recursive)
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _iter_files(self, base: Path) -> Iterable[Path]:
        if self.recursive:
            stack = [base]
            while stack and not self._stop_event.is_set():
                d = stack.pop()
                try:
                    entries = list(os.scandir(d))
                except Exception:
                    continue
                entries.sort(key=lambda e: e.name.lower(), reverse=True)
                for entry in entries:
                    if self._stop_event.is_set():
                        break
                    try:
                        if entry.is_file(follow_symlinks=False):
                            yield Path(entry.path)
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except Exception:
                        continue
        else:
            try:
                entries = list(os.scandir(base))
            except Exception:
                entries = []
            entries.sort(key=lambda e: e.name.lower())
            for entry in entries:
                if self._stop_event.is_set():
                    break
                try:
                    if entry.is_file(follow_symlinks=False):
                        yield Path(entry.path)
                except Exception:
                    continue

    def run(self):
        try:
            base = Path(self.folder)
            if not base.exists() or not base.is_dir():
                self.scan_error.emit(self.scan_id, t("Folder does not exist or is not a directory"))
                return
            for fp in self._iter_files(base):
                if self._stop_event.is_set():
                    break
                self.file_found.emit(self.scan_id, str(fp))
            self.scan_done.emit(self.scan_id)
        except Exception as e:
            self.scan_error.emit(self.scan_id, str(e))


class UndoSignals(QtCore.QObject):
    # Carries (restored, failed, gone) lists from the undo worker to the UI.
    # "gone" = the file has left the category folder (moved/deleted by
    # hand) — nothing to restore, must never be re-queued.
    finished = Signal(object, object, object)


class TransferSignals(QtCore.QObject):
    transfer_started = Signal(str, str)
    transfer_finished = Signal(str, str)
    transfer_error = Signal(str, str)
    queue_updated = Signal(int, int)


class TransferManager(QtCore.QObject):
    def __init__(self, max_workers: int = 4):
        super().__init__()
        self.max_workers = max(1, int(max_workers))
        self.queue = deque()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_futures = {}
        self.signals = TransferSignals()
        self._lock = threading.RLock()
        self._cancel_generation = 0
        self._known_sources = set()
        self._reserved_destinations = set()
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def enqueue(self, src: str, dst_dir: str) -> bool:
        src = str(Path(src))
        dst_dir = str(Path(dst_dir).expanduser())
        with self._lock:
            if src in self._known_sources:
                return False
            self._known_sources.add(src)
            self.queue.append((src, dst_dir))
            queued, active = len(self.queue), len(self.active_futures)
        self.signals.queue_updated.emit(queued, active)
        return True

    def cancel_all(self) -> int:
        """Drop every queued (not yet started) transfer and cancel the active ones.

        Returns the number of queued items that were dropped WITHOUT ever
        starting — they will never emit finished/error, so the caller (the
        undo-batch bookkeeping) must not wait for them.
        """
        dropped = 0
        with self._lock:
            while self.queue:
                src, _ = self.queue.popleft()
                self._known_sources.discard(src)
                dropped += 1
            self._cancel_generation += 1
            futures = list(self.active_futures.keys())
            queued, active = len(self.queue), len(self.active_futures)
        for fut in futures:
            try:
                fut.cancel()
            except Exception:
                pass
        self.signals.queue_updated.emit(queued, active)
        return dropped

    def is_idle(self) -> bool:
        """True when nothing is queued and nothing is running."""
        with self._lock:
            return not self.queue and not self.active_futures

    def shutdown(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self.cancel_all()
        except Exception:
            pass
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self.executor.shutdown(wait=False)
        except Exception:
            pass

    def _is_cancelled(self, generation: int) -> bool:
        with self._lock:
            return generation != self._cancel_generation

    def _tick(self):
        starts = []
        try:
            with self._lock:
                while self.queue and len(self.active_futures) < self.max_workers:
                    src, dst_dir = self.queue.popleft()
                    generation = self._cancel_generation
                    fut = self.executor.submit(self._do_move, src, dst_dir, generation)
                    self.active_futures[fut] = (src, dst_dir)
                    fut.add_done_callback(self._on_done)
                    starts.append((src, dst_dir))
                queued, active = len(self.queue), len(self.active_futures)
            for src, dst_dir in starts:
                self.signals.transfer_started.emit(src, dst_dir)
            self.signals.queue_updated.emit(queued, active)
        except Exception:
            traceback.print_exc()

    def _on_done(self, fut):
        with self._lock:
            info = self.active_futures.pop(fut, None)
            if info:
                self._known_sources.discard(info[0])
            queued, active = len(self.queue), len(self.active_futures)
        if not info:
            self.signals.queue_updated.emit(queued, active)
            return
        src, _dst_dir = info
        # IMPORTANT: the per-item outcome (finished/error) must be emitted
        # BEFORE the queue-count update. The UI closes the undo batch as soon
        # as it sees (queued=0, active=0); if the count arrived first, the
        # last file of every round would be sealed out of the undo batch.
        if fut.cancelled():
            self.signals.transfer_error.emit(src, t("Cancelled"))
        else:
            try:
                new_path = fut.result()
            except Exception as exc:
                self.signals.transfer_error.emit(src, str(exc))
            else:
                self.signals.transfer_finished.emit(src, new_path)
        self.signals.queue_updated.emit(queued, active)

    def _reserve_destination(self, src_p: Path, dst_dir_p: Path) -> Path:
        dst_dir_p.mkdir(parents=True, exist_ok=True)
        wanted = dst_dir_p / src_p.name
        with self._lock:
            dst = unique_destination(wanted, self._reserved_destinations)
            self._reserved_destinations.add(str(dst))
        return dst

    def _release_destination(self, dst: Path) -> None:
        with self._lock:
            self._reserved_destinations.discard(str(dst))

    def _copy_exclusive_then_remove(self, src_p: Path, dst: Path, generation: int) -> str:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(str(dst), flags, 0o666)
        try:
            with open(src_p, "rb") as fsrc, os.fdopen(fd, "wb") as fdst:
                fd = None
                while True:
                    if self._is_cancelled(generation):
                        raise RuntimeError(t("Cancelled"))
                    chunk = fsrc.read(TRANSFER_CHUNK_SIZE)
                    if not chunk:
                        break
                    fdst.write(chunk)
                try:
                    fdst.flush(); os.fsync(fdst.fileno())
                except Exception:
                    pass
            try:
                shutil.copystat(str(src_p), str(dst), follow_symlinks=False)
            except Exception:
                pass
            if self._is_cancelled(generation):
                raise RuntimeError(t("Cancelled"))
            # Cross-drive fallback copy: verify the copy is complete (size)
            # before destroying the source. On a mismatch the exception path
            # below removes the partial destination and the source survives.
            if dst.stat().st_size != src_p.stat().st_size:
                raise RuntimeError(t("Copy size mismatch — the original file was kept"))
            force_unlink(src_p)
            return str(dst)
        except Exception:
            if fd is not None:
                try: os.close(fd)
                except Exception: pass
            try:
                if dst.exists():
                    force_unlink(dst)
            except Exception:
                pass
            raise

    def _do_move(self, src: str, dst_dir: str, generation: int) -> str:
        if self._is_cancelled(generation):
            raise RuntimeError(t("Cancelled"))
        src_p = Path(src)
        dst_dir_p = Path(dst_dir).expanduser()
        if not src_p.exists() or not src_p.is_file():
            raise RuntimeError(t("Source file does not exist"))
        if same_path(src_p.parent, dst_dir_p):
            raise RuntimeError(t("File is already in the destination folder"))
        dst = self._reserve_destination(src_p, dst_dir_p)
        try:
            if self._is_cancelled(generation):
                raise RuntimeError(t("Cancelled"))
            linked = False
            try:
                was_readonly = not (src_p.stat().st_mode & stat.S_IWRITE)
                os.link(str(src_p), str(dst))
                linked = True
                if self._is_cancelled(generation):
                    raise RuntimeError(t("Cancelled"))
                force_unlink(src_p)
                if was_readonly:
                    # Both hardlinks share the Windows read-only attribute;
                    # force_unlink() had to clear it on the source, so give
                    # the moved copy its attribute back.
                    try:
                        os.chmod(str(dst), stat.S_IREAD)
                    except OSError:
                        pass
                return str(dst)
            except RuntimeError:
                if linked:
                    try: force_unlink(dst)
                    except Exception: pass
                raise
            except Exception:
                if linked:
                    try: force_unlink(dst)
                    except Exception: pass
            return self._copy_exclusive_then_remove(src_p, dst, generation)
        finally:
            self._release_destination(dst)


class QtVideoWidget(QtWidgets.QFrame):
    """Embedded video surface on Qt Multimedia — no external runtime needed.

    Uses the FFmpeg backend that ships inside the PyQt6/PySide6 wheels, so a
    clean Windows PC plays videos in-app with zero extra installs. Playback
    errors surface through errorOccurred and make has_video_frame() return
    False, which triggers the libVLC -> ffplay fallbacks in the main window.

    Clips loop: when they reach the end they restart from the beginning
    automatically (setLoops(-1), with a manual EndOfMedia fallback).
    """

    # Emitted whenever the clip reaches its end (before looping restarts it).
    ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Preview")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.video_surface = QVideoWidget(self)
        lay.addWidget(self.video_surface)
        self.player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_out)
        # CRITICAL: creating a QVideoWidget does NOT attach it to the player.
        # Without setVideoOutput the audio plays but the picture is never
        # rendered (a black surface) — the classic "video won't display" bug.
        self.player.setVideoOutput(self.video_surface)
        self.audio_out.setVolume(1.0)
        self._failed = False
        self._loop_ok = False
        self.player.errorOccurred.connect(self._on_error)
        try:
            self.player.mediaStatusChanged.connect(self._on_media_status)
        except Exception:
            pass
        # Loop playback: when the video ends it restarts from the beginning
        # automatically. setLoops(-1) is the native Qt way (Qt >= 6.1);
        # _on_media_status keeps a manual fallback for older builds.
        try:
            self.player.setLoops(-1)
            self._loop_ok = True
        except Exception:
            self._loop_ok = False
        self.setMinimumSize(320, 240)

    def _on_error(self, err, err_str=""):
        self._failed = True
        log_exception("QtMediaPlayer error", RuntimeError(f"{err}: {err_str}"))

    def _on_media_status(self, status):
        try:
            if MEDIA_INVALID is not None and _enum_int(status) == _enum_int(MEDIA_INVALID):
                self._failed = True
            if MEDIA_END is not None and _enum_int(status) == _enum_int(MEDIA_END):
                try:
                    self.ended.emit()
                except Exception:
                    pass
                if not self._loop_ok:
                    # Manual loop fallback: rewind and play again.
                    try:
                        self.player.setPosition(0)
                        self.player.play()
                    except Exception:
                        pass
        except Exception:
            pass

    def play(self, path: str):
        self._failed = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def has_video_frame(self) -> bool:
        try:
            if self._failed:
                return False
            src = self.player.source()
            if src is None or src.isEmpty():
                return False
            try:
                if MEDIA_NOERROR is not None and _enum_int(self.player.error()) != _enum_int(MEDIA_NOERROR):
                    return False
            except Exception:
                pass
            try:
                ms = _enum_int(self.player.mediaStatus())
                if MEDIA_NOMEDIA is not None and ms == _enum_int(MEDIA_NOMEDIA):
                    return False
                if MEDIA_INVALID is not None and ms == _enum_int(MEDIA_INVALID):
                    return False
            except Exception:
                pass
            return True
        except Exception:
            return False

    def pause_or_resume(self) -> bool:
        try:
            playing = _enum_int(self.player.playbackState()) == _enum_int(QMediaPlayer.PlaybackState.PlayingState)
        except Exception:
            playing = False
        if playing:
            self.player.pause()
            return False
        self.player.play()
        return True

    def stop(self):
        try:
            self.player.stop()
            # Clear the source so the file handle is released immediately
            # (mirrors the libVLC stop behaviour; needed before moving files).
            self.player.setSource(QUrl())
        except Exception:
            pass

    def cleanup(self):
        self.stop()


class VLCWidget(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Preview")
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.instance = None
        self.player = None
        self.setMinimumSize(320, 240)
        self.setAttribute(WA_NATIVE_WINDOW, True)

    def ensure(self) -> bool:
        if not VLC_AVAILABLE:
            return False
        if self.player is not None:
            return True
        try:
            args = ["--no-video-title-show", "--quiet"]
            vdir = portable_vlc_dir()
            if vdir and (vdir / "plugins").exists():
                args.append("--plugin-path=" + str(vdir / "plugins"))
            self.instance = vlc.Instance(args)
            self.player = self.instance.media_player_new()
            self._bind_output()
            return True
        except Exception as e:
            log_exception("VLC init failed", e)
            return False

    def _bind_output(self):
        if not self.player:
            return
        try:
            self.setAttribute(WA_NATIVE_WINDOW, True)
            self.winId()  # force native handle creation
            win_id = int(self.winId())
            if sys.platform == "win32":
                self.player.set_hwnd(win_id)
            elif sys.platform.startswith("linux"):
                self.player.set_xwindow(win_id)
            elif sys.platform == "darwin":
                self.player.set_nsobject(win_id)
        except Exception as e:
            log_exception("VLC video output bind failed", e)

    def has_video_frame(self) -> bool:
        try:
            if not self.player:
                return False
            if hasattr(self.player, "video_get_size"):
                sz = self.player.video_get_size(0)
                if isinstance(sz, tuple) and len(sz) >= 2 and sz[0] > 0 and sz[1] > 0:
                    return True
            if hasattr(self.player, "video_get_width") and hasattr(self.player, "video_get_height"):
                return self.player.video_get_width() > 0 and self.player.video_get_height() > 0
        except Exception:
            pass
        return False

    def play(self, path: str):
        if not self.ensure():
            raise RuntimeError("VLC not available")
        self.show()
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        self._bind_output()
        media = self.instance.media_new(str(path))
        # Loop: when the clip ends, libVLC restarts it from the beginning.
        try:
            media.add_option("input-repeat=65535")
        except Exception:
            pass
        try: self.player.stop()
        except Exception: pass
        self.player.set_media(media)
        self._bind_output()
        self.player.play()

    def pause_or_resume(self) -> bool:
        if not self.player:
            return False
        try:
            # get_state() is reliable; is_playing() can report stale values
            # right after a pause. set_pause() is explicit — no toggle race.
            state = self.player.get_state()
            if state == vlc.State.Paused:
                self.player.set_pause(False)  # resume
                return True
            if state == vlc.State.Playing:
                self.player.set_pause(True)   # pause
                return False
            self.player.play()  # stopped/ended — start again from the beginning
            return True
        except Exception:
            return False

    def stop(self):
        try:
            if self.player:
                try:
                    self.player.stop()
                except Exception:
                    pass
                # Drop media so libVLC releases the file handle (stop is async on Windows).
                try:
                    self.player.set_media(None)
                except Exception:
                    pass
        except Exception:
            pass

    def cleanup(self):
        try:
            if self.player:
                try: self.player.stop()
                except Exception: pass
                try:
                    if hasattr(self.player, "release"):
                        self.player.release()
                except Exception: pass
                self.player = None
            if self.instance:
                try:
                    if hasattr(self.instance, "release"):
                        self.instance.release()
                except Exception: pass
                self.instance = None
        except Exception:
            pass


class SortView(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Just the product name — the active Qt binding is an implementation
        # detail (and is written to app.log at startup for support).
        self.setWindowTitle("SortView")
        self.resize(1380, 860)
        if APP_ICON.exists():
            self.setWindowIcon(QIcon(str(APP_ICON)))

        self.config = self._load_config()
        saved_folder = str(self.config.get("candidate_folder", "")).strip()
        self._folder_user_selected = bool(self.config.get("folder_user_selected", False))
        # Old builds wrote a default path to config without a user action. Ignore
        # any stored candidate folder unless the current config explicitly says the
        # user selected it. This makes the real first launch completely path-less.
        if not self._folder_user_selected:
            saved_folder = ""
        if saved_folder:
            try:
                sp = Path(saved_folder).expanduser()
                if sp.name.lower() == "to_sort" and sp.parent.name.lower() == "desktop":
                    saved_folder = ""
                    self._folder_user_selected = False
            except Exception:
                pass
        self.candidate_folder = Path(saved_folder).expanduser() if saved_folder else None
        # Last directory the user actually browsed to (folder picker / category path).
        # Empty on first run so dialogs do not open at Path.home() (e.g. WDAGUtilityAccount).
        self.last_browse_dir = str(self.config.get("last_browse_dir", "")).strip() or ""
        self.include_subfolders = bool(self.config.get("include_subfolders", False))
        self.categories = normalize_categories(self.config.get("categories", []))
        self.thumbnail_size = int(self.config.get("thumb_size", DEFAULT_THUMB))
        self.theme_name = self.config.get("theme", "dark") if self.config.get("theme", "dark") in THEMES else "dark"

        self.path_to_item = {}
        self._scan_buffer = []
        self._scan_generation = 0
        self._thumbnail_generation = 0
        self._current_filter_exts: List[str] = []
        self._last_transfer_initiator_preview = None
        self.preview_movie = None
        self._preview_original_pixmap = None
        self.external_player_proc = None
        self.transfers_completed = 0
        self.transfers_failed = 0
        self._thumb_inflight = 0

        # Undo of transfer rounds: every completed round is recorded as
        # (original_source, final_destination) pairs, newest last. Ctrl+Z or
        # the Undo move button replays the newest batch in a worker thread
        # and rescans the folder so the files reappear in the explorer grid.
        self._undo_stack: deque = deque(maxlen=50)
        self._undo_pending: List[Tuple[str, str]] = []
        self._undo_batch_open = False
        self._undo_active = False
        # Race guard for closing the undo batch: count how many files this
        # batch expects (every successful enqueue while the batch is open)
        # and how many have reported back (transfer_finished OR transfer_error,
        # both run on the UI thread). The batch may only be sealed when every
        # expected file reported — a queue_updated(0, 0) that arrives from the
        # TransferManager's 150 ms tick between a worker popping the last
        # future and the UI processing its transfer_finished event must NOT
        # seal the batch, or the last file would be locked out of Ctrl+Z.
        self._undo_expected = 0
        self._undo_done = 0
        self.undo_signals = UndoSignals()
        self.undo_signals.finished.connect(self._on_undo_finished)

        self.thumb_signals = ThumbSignals()
        self.thumb_signals.finished.connect(self._on_thumb_finished)
        self.thumb_executor = ThreadPoolExecutor(max_workers=THUMB_MAX_WORKERS)
        self.thumb_queue = deque()
        self.thumb_submit_timer = QTimer(self)
        self.thumb_submit_timer.setInterval(40)
        self.thumb_submit_timer.timeout.connect(self._submit_thumb_batch)
        self.thumb_submit_timer.start()

        self._populate_files: List[Path] = []
        self._populate_index = 0
        self.populate_timer = QTimer(self)
        self.populate_timer.setInterval(0)
        self.populate_timer.timeout.connect(self._populate_next_batch)

        self._type_icon_cache = {}
        self._thumb_queued_paths = set()
        self._thumb_processing_paths = set()
        self._thumb_done_paths = set()
        self._background_thumb_index = 0
        self._playback_active = False
        self._audio_mode = False  # Qt engine playing an audio-only file
        self.visible_thumb_timer = QTimer(self)
        self.visible_thumb_timer.setSingleShot(True)
        self.visible_thumb_timer.setInterval(45)
        self.visible_thumb_timer.timeout.connect(self._queue_visible_thumbnails)
        self.background_thumb_timer = QTimer(self)
        self.background_thumb_timer.setInterval(180)
        self.background_thumb_timer.timeout.connect(self._queue_background_thumbnails)

        # Keep transfers off the UI thread, but limit parallel disk IO so the app stays responsive.
        self.transfer_mgr = TransferManager(max_workers=2)
        self.transfer_mgr.signals.transfer_started.connect(self._on_transfer_started)
        self.transfer_mgr.signals.transfer_finished.connect(self._on_transfer_finished)
        self.transfer_mgr.signals.transfer_error.connect(self._on_transfer_error)
        self.transfer_mgr.signals.queue_updated.connect(self._on_transfer_queue_updated)

        self.scanner = None
        self._setup_ui()
        self._connect_signals()
        self.apply_theme(self.theme_name)
        self._save_config()
        self.load_files()
        # The 0–9 digit shortcuts are the core interaction: give the file grid
        # the initial keyboard focus so a fresh start can move files right
        # away — the theme combo is the first focusable widget in the header
        # and would otherwise silently swallow the digits.
        try:
            self.list_widget.setFocus()
        except Exception:
            pass

    # ---------------- config ----------------
    def _load_config(self):
        try:
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception as e:
            # config.json is unreadable (crash/power loss during a past write,
            # disk error, manual edit). Do NOT silently overwrite it: move it
            # aside so the user can still recover their categories, and log it.
            try:
                backup = CONFIG_FILE.with_name(CONFIG_FILE.name + ".corrupt")
                CONFIG_FILE.replace(backup)
                log_exception(f"config.json was unreadable; moved to {backup.name}", e)
            except Exception:
                log_exception("config.json was unreadable and could not be backed up", e)
        return {}

    def _save_config(self):
        try:
            self.config["candidate_folder"] = str(self.candidate_folder) if self.candidate_folder and self._folder_user_selected else ""
            self.config["folder_user_selected"] = bool(self._folder_user_selected and self.candidate_folder)
            self.config["last_browse_dir"] = str(getattr(self, "last_browse_dir", "") or "")
            self.config["include_subfolders"] = bool(self.include_subfolders)
            self.config["categories"] = normalize_categories(self.categories)
            self.config["thumb_size"] = int(self.thumbnail_size)
            self.config["theme"] = self.theme_name
            self.config["language"] = app_i18n.get_language()
            payload = json.dumps(self.config, ensure_ascii=False, indent=2)
            # Write atomically: temp file in the same folder, flushed to disk,
            # then os.replace() which is atomic on Windows and POSIX. A crash
            # mid-write can now only leave the OLD config intact (plus a
            # leftover .tmp), never a half-written config.json.
            tmp = CONFIG_FILE.with_name(CONFIG_FILE.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, CONFIG_FILE)
        except Exception as e:
            log_exception("saving config.json failed", e)

    def _remember_browse_dir(self, folder: str):
        """Remember the last directory the user picked in a folder dialog."""
        try:
            folder = str(folder or "").strip()
            if not folder:
                return
            p = Path(folder).expanduser()
            # Prefer the directory itself if it is a dir; else its parent.
            if p.is_file():
                p = p.parent
            if p.exists() and p.is_dir():
                self.last_browse_dir = str(p)
            else:
                # Still store the path text so next dialog starts near it.
                self.last_browse_dir = str(p)
            self.config["last_browse_dir"] = self.last_browse_dir
            self._save_config()
        except Exception:
            pass

    def _browse_start_dir(self, preferred: str = "") -> str:
        """Directory to open file/folder dialogs at. Empty string = OS default (no forced home)."""
        preferred = str(preferred or "").strip()
        if preferred:
            try:
                p = Path(preferred).expanduser()
                if p.is_file():
                    p = p.parent
                if p.exists() and p.is_dir():
                    return str(p)
                # Non-existing but non-empty path: still useful as dialog start hint
                if preferred:
                    return preferred
            except Exception:
                pass
        return str(getattr(self, "last_browse_dir", "") or "")

    # ---------------- UI ----------------
    def _panel(self) -> QtWidgets.QFrame:
        f = QtWidgets.QFrame()
        f.setObjectName("Panel")
        return f

    def _setup_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        header = self._panel()
        header_l = QtWidgets.QHBoxLayout(header)
        header_l.setContentsMargins(16, 12, 16, 12)
        header_l.setSpacing(12)
        header_icon = QtWidgets.QLabel()
        header_icon.setObjectName("HeaderIcon")
        if APP_ICON.exists():
            _pm = QPixmap(str(APP_ICON))
            if not _pm.isNull():
                header_icon.setPixmap(_pm.scaled(46, 46, KEEP_ASPECT, SMOOTH))
        header_l.addWidget(header_icon)
        title_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("SortView")
        title.setObjectName("Title")
        self.subtitle = QtWidgets.QLabel(t("Fast browsing, previews & safe file transfers"))
        self.subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(self.subtitle)
        header_l.addLayout(title_box)
        header_l.addStretch()
        # Theme & language live in one themed "chip". With six themes the old
        # segmented buttons grew past 700 px, so they became two compact combo
        # boxes instead; every theme item carries a two-colour circle so the
        # palette is visible before choosing it.
        tools = QtWidgets.QFrame()
        tools.setObjectName("HeaderTools")
        tools_l = QtWidgets.QHBoxLayout(tools)
        tools_l.setContentsMargins(12, 6, 12, 6)
        tools_l.setSpacing(6)
        self.lbl_theme = QtWidgets.QLabel(t("Theme"))
        self.lbl_theme.setObjectName("FieldLabel")
        tools_l.addWidget(self.lbl_theme)
        _sap = _qt_value(QtWidgets.QComboBox, "SizeAdjustPolicy", "AdjustToContents")
        self.theme_combo = HeaderCombo()
        try:
            self.theme_combo.setSizeAdjustPolicy(_sap)
        except Exception:
            pass
        for _name in THEMES:
            # The label is translated (Persian UI shows روشن / کاغذی / گرافیتی /
            # تیره / جنگلی / مشکی خالص); the real theme key is kept as item data
            # so apply_theme can still match it after a language switch.
            self.theme_combo.addItem(theme_color_icon(_name), t(THEMES[_name].get("label", _name)), _name)
        _idx = self.theme_combo.findData(self.theme_name)
        self.theme_combo.setCurrentIndex(_idx if _idx >= 0 else 0)
        if POINTING_HAND is not None:
            self.theme_combo.setCursor(QtGui.QCursor(POINTING_HAND))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        tools_l.addWidget(self.theme_combo)
        chip_sep = QtWidgets.QFrame()
        chip_sep.setObjectName("ChipSeparator")
        chip_sep.setFixedSize(1, 18)
        tools_l.addWidget(chip_sep)
        self.lbl_language = QtWidgets.QLabel(t("Language"))
        self.lbl_language.setObjectName("FieldLabel")
        tools_l.addWidget(self.lbl_language)
        self.lang_combo = HeaderCombo()
        try:
            self.lang_combo.setSizeAdjustPolicy(_sap)
        except Exception:
            pass
        for _code, _label in app_i18n.LANGUAGES:
            # Every language is listed under its own native name; the real
            # language code is kept as item data.
            self.lang_combo.addItem(_label, _code)
        self.lang_combo.setCurrentIndex(0 if app_i18n.get_language() == "en" else 1)
        if POINTING_HAND is not None:
            self.lang_combo.setCursor(QtGui.QCursor(POINTING_HAND))
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        tools_l.addWidget(self.lang_combo)
        header_l.addWidget(tools)
        root.addWidget(header)

        splitter = QtWidgets.QSplitter()
        root.addWidget(splitter, 1)

        # left panel
        left_panel = self._panel()
        left_l = QtWidgets.QVBoxLayout(left_panel)
        left_l.setContentsMargins(10, 10, 10, 10)
        left_l.setSpacing(8)
        row1 = QtWidgets.QHBoxLayout()
        self.btn_change_folder = QtWidgets.QPushButton(t("Change folder"))
        self.btn_change_folder.setObjectName("PrimaryBtn")
        row1.addWidget(self.btn_change_folder)
        self.btn_refresh = QtWidgets.QPushButton(t("Refresh"))
        row1.addWidget(self.btn_refresh)
        left_l.addLayout(row1)
        self.folder_label = QtWidgets.QLabel(self._folder_label_text())
        self.folder_label.setObjectName("Muted")
        self.folder_label.setTextInteractionFlags(TEXT_SELECTABLE)
        self.folder_label.setWordWrap(True)
        left_l.addWidget(self.folder_label)

        row2 = QtWidgets.QHBoxLayout()
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText(t("Filter: .jpg,.png,.mp4 or empty"))
        row2.addWidget(self.filter_edit, 1)
        self.sort_combo = HeaderCombo()
        self.sort_combo.addItems([t("Name"), t("Type")])
        row2.addWidget(self.sort_combo)
        left_l.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        self.lbl_thumb = QtWidgets.QLabel(t("Thumb:"))
        row3.addWidget(self.lbl_thumb)
        self.thumb_slider = QtWidgets.QSlider(HORIZONTAL)
        self.thumb_slider.setMinimum(72)
        self.thumb_slider.setMaximum(420)
        self.thumb_slider.setValue(self.thumbnail_size)
        row3.addWidget(self.thumb_slider, 1)
        self.thumb_size_label = QtWidgets.QLabel(str(self.thumbnail_size))
        row3.addWidget(self.thumb_size_label)
        left_l.addLayout(row3)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setViewMode(ViewMode_Icon)
        self.list_widget.setMovement(Movement_Static)
        self.list_widget.setIconSize(QSize(self.thumbnail_size, self.thumbnail_size))
        self.list_widget.setResizeMode(Resize_Adjust)
        self.list_widget.setSpacing(7)
        self.list_widget.setSelectionMode(Selection_Extended)
        left_l.addWidget(self.list_widget, 1)
        splitter.addWidget(left_panel)

        # center preview
        preview_panel = QtWidgets.QFrame()
        preview_panel.setObjectName("PreviewPanel")
        center_l = QtWidgets.QVBoxLayout(preview_panel)
        center_l.setContentsMargins(10, 10, 10, 10)
        self.preview_label = QtWidgets.QLabel(t("Preview"))
        self.preview_label.setObjectName("Preview")
        self.preview_label.setAlignment(ALIGN_CENTER)
        self.preview_label.setMinimumSize(520, 390)
        center_l.addWidget(self.preview_label, 1)
        self.vlc_frame = VLCWidget()
        self.vlc_frame.hide()
        center_l.addWidget(self.vlc_frame, 1)
        self.qt_video = None
        if HAS_QTMEDIA:
            try:
                self.qt_video = QtVideoWidget()
                self.qt_video.hide()
                center_l.addWidget(self.qt_video, 1)
            except Exception as e:
                log_exception("Qt Multimedia init failed", e)
                self.qt_video = None
        ctrl_h = QtWidgets.QHBoxLayout()
        self.play_btn = QtWidgets.QPushButton(t("Play / Pause"))
        self.stop_btn = QtWidgets.QPushButton(t("Stop"))
        self.btn_open_ext = QtWidgets.QPushButton(t("Open with system player"))
        self.btn_open_ext.setToolTip(t("Open the selected file with the default Windows app"))
        ctrl_h.addStretch()
        ctrl_h.addWidget(self.play_btn)
        ctrl_h.addWidget(self.stop_btn)
        ctrl_h.addWidget(self.btn_open_ext)
        ctrl_h.addStretch()
        center_l.addLayout(ctrl_h)
        splitter.addWidget(preview_panel)

        # right panel
        right_panel = self._panel()
        right_l = QtWidgets.QVBoxLayout(right_panel)
        right_l.setContentsMargins(10, 10, 10, 10)
        right_l.setSpacing(8)
        self.lbl_cat = QtWidgets.QLabel(t("Categories"))
        self.lbl_cat.setObjectName("Title")
        right_l.addWidget(self.lbl_cat)
        # Merged category panel (1.9.0): the old design showed every category
        # twice — once in a plain list, once as a quick move button — which ate
        # vertical space and made the two views feel redundant. Now each
        # category IS a single button in one scrollable list:
        #   click       = move the selected files into that category
        #   right-click = Edit / Remove / Move up / Move down for that category
        # The first ten buttons keep their "0:"–"9:" badge and the matching
        # digit shortcuts; categories beyond ten are plain buttons (a "12:"
        # badge would suggest a key that does not exist).
        self.quick_lbl = QtWidgets.QLabel(t("Click: move selected files • Right-click: edit / remove / reorder"))
        self.quick_lbl.setObjectName("Muted")
        self.quick_lbl.setWordWrap(True)
        right_l.addWidget(self.quick_lbl)
        self.quick_scroll = QtWidgets.QScrollArea()
        self.quick_scroll.setWidgetResizable(True)
        self.quick_container = QtWidgets.QWidget()
        self.quick_layout = QtWidgets.QVBoxLayout(self.quick_container)
        self.quick_layout.setAlignment(ALIGN_TOP)
        self.quick_scroll.setWidget(self.quick_container)
        right_l.addWidget(self.quick_scroll, 1)
        # The "+ Add Category" button lives BELOW the scroll area, not inside
        # it: inside the scrolling region it got clipped half-away and scrolled
        # out of sight whenever the category list grew long.
        self.btn_add_quick = QtWidgets.QPushButton(t("+ Add Category"))
        self.btn_add_quick.setObjectName("PrimaryBtn")
        self.btn_add_quick.clicked.connect(self.add_category)
        right_l.addWidget(self.btn_add_quick)
        sets_h = QtWidgets.QHBoxLayout()
        self.btn_save_set = QtWidgets.QPushButton(t("Save set"))
        self.btn_load_set = QtWidgets.QPushButton(t("Load set"))
        sets_h.addWidget(self.btn_save_set); sets_h.addWidget(self.btn_load_set)
        right_l.addLayout(sets_h)
        sets2_h = QtWidgets.QHBoxLayout()
        self.btn_export_set = QtWidgets.QPushButton(t("Export"))
        self.btn_import_set = QtWidgets.QPushButton(t("Import"))
        sets2_h.addWidget(self.btn_export_set); sets2_h.addWidget(self.btn_import_set)
        right_l.addLayout(sets2_h)
        self.btn_save_set.clicked.connect(self.save_category_set); self.btn_load_set.clicked.connect(self.load_category_set)
        self.btn_export_set.clicked.connect(self.export_category_set_to_file); self.btn_import_set.clicked.connect(self.import_category_set_from_file)
        self.btn_clear_thumbs = QtWidgets.QPushButton(t("Clear thumbnail cache"))
        right_l.addWidget(self.btn_clear_thumbs)
        # Undo of the last transfer round. Always visible (disabled while the
        # undo stack is empty) so it can be discovered; Ctrl+Z does the same.
        self.btn_undo = QtWidgets.QPushButton(t("Undo move"))
        self.btn_undo.setToolTip(t("Move the files of the last transfer back to their original folder (Ctrl+Z)"))
        self.btn_undo.setEnabled(False)
        right_l.addWidget(self.btn_undo)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.hide()  # idle — the bar only shows while a scan runs
        right_l.addWidget(self.progress)
        self.status = QtWidgets.QLabel(t("Ready"))
        self.status.setObjectName("StatusLabel")
        self.status.setWordWrap(True)
        right_l.addWidget(self.status)
        self.btn_cancel_all = QtWidgets.QPushButton(t("Cancel transfers"))
        self.btn_cancel_all.setObjectName("DangerBtn")
        self.btn_cancel_all.hide()
        right_l.addWidget(self.btn_cancel_all)
        splitter.addWidget(right_panel)
        splitter.setSizes([500, 620, 300])

        self.total_files_label = QtWidgets.QLabel(t("Total: {n}").format(n=0))
        self.transfer_busy_label = QtWidgets.QLabel(t("Busy: No"))
        self.transfer_done_label = QtWidgets.QLabel(t("Done: {n}").format(n=0))
        self.transfer_queue_label = QtWidgets.QLabel(t("Queued: {n}").format(n=0))
        self.transfer_failed_label = QtWidgets.QLabel(t("Failed: {n}").format(n=0))
        self.transfer_active_label = QtWidgets.QLabel(t("Active: {n}").format(n=0))
        for w in (self.total_files_label, self.transfer_busy_label, self.transfer_queue_label, self.transfer_done_label, self.transfer_failed_label, self.transfer_active_label):
            self.statusBar().addPermanentWidget(w)

        self._refresh_categories_ui()

    def _connect_signals(self):
        self.btn_change_folder.clicked.connect(self.change_folder)
        self.btn_refresh.clicked.connect(self.load_files)
        self.btn_clear_thumbs.clicked.connect(self.clear_thumbnail_cache)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self.open_file)
        try:
            self.list_widget.verticalScrollBar().valueChanged.connect(lambda _=None: self.visible_thumb_timer.start())
            self.list_widget.horizontalScrollBar().valueChanged.connect(lambda _=None: self.visible_thumb_timer.start())
        except Exception:
            pass
        self.play_btn.clicked.connect(self._play_or_pause)
        self.stop_btn.clicked.connect(self._stop_video)
        self.btn_open_ext.clicked.connect(self.open_selected_with_system_player)
        # Keep the Play/Pause label truthful for every engine: when a clip
        # ends or loops, the button must flip back to "Play" instead of
        # staying "Pause" (which made pressing it look like a restart).
        self.playback_sync_timer = QTimer(self)
        self.playback_sync_timer.setInterval(400)
        self.playback_sync_timer.timeout.connect(self._sync_playback_button)
        self.playback_sync_timer.start()
        if getattr(self, "qt_video", None) is not None:
            try:
                self.qt_video.player.playbackStateChanged.connect(lambda *_: self._sync_playback_button())
            except Exception:
                pass
            try:
                self.qt_video.ended.connect(self._sync_playback_button)
            except Exception:
                pass
        self.sort_combo.currentIndexChanged.connect(lambda _: self.load_files())
        self.btn_cancel_all.clicked.connect(self._cancel_all_transfers)
        self.btn_undo.clicked.connect(self._undo_last_move)
        self.filter_timer = QTimer(self); self.filter_timer.setSingleShot(True); self.filter_timer.setInterval(350)
        self.filter_timer.timeout.connect(self.load_files)
        self.filter_edit.textChanged.connect(lambda: self.filter_timer.start())
        self.thumb_apply_timer = QTimer(self); self.thumb_apply_timer.setSingleShot(True); self.thumb_apply_timer.setInterval(280)
        self.thumb_apply_timer.timeout.connect(self._apply_pending_thumb_size)
        self._pending_thumb_size = self.thumbnail_size
        self.thumb_slider.valueChanged.connect(self._on_thumb_slider_changed)
        if QShortcut is not None:
            for k in range(10):
                sc = QShortcut(QKeySequence(str(k)), self, activated=partial(self._on_key_shortcut, k))
                try:
                    sc.setAutoRepeat(False)
                except Exception:
                    pass
            # Ctrl+Z = undo the last transfer round (the standard Undo key).
            sc_undo = QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo_last_move)
            try:
                sc_undo.setAutoRepeat(False)
            except Exception:
                pass

    def apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            theme_name = "dark"
        self.theme_name = theme_name
        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyleSheet(build_qss(theme_name))
            # The palette fixes every widget the QSS does not explicitly cover
            # (spin boxes, disabled text, native popups) — otherwise they kept
            # the light Windows palette and looked wrong inside dark dialogs.
            try:
                app.setPalette(build_palette(theme_name))
            except Exception:
                pass
            # Native title bars must follow the theme too (white dialog title
            # bars were the most visible mismatch on Windows). The colour
            # scheme covers every window on Qt >= 6.8; the direct DWM call
            # also themes the main window on older builds.
            try:
                dark = theme_name != "light"
                _apply_app_color_scheme(dark)
                _apply_windows_titlebar(self, dark)
            except Exception:
                pass
        combo = getattr(self, "theme_combo", None)
        if combo is not None:
            try:
                idx = combo.findData(theme_name)
                if idx >= 0 and combo.currentIndex() != idx:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
            except Exception:
                pass
        # Recolour the painted drop arrows (HeaderCombo) for the new theme.
        try:
            _muted = THEMES[theme_name]["muted"]
            for _cb in ("theme_combo", "lang_combo", "sort_combo"):
                _w = getattr(self, _cb, None)
                if _w is not None:
                    _w.arrow_color = _muted
        except Exception:
            pass
        self._save_config()

    def _on_theme_combo_changed(self, index: int):
        """Apply the theme whose key is stored as the combo item's data."""
        try:
            key = self.theme_combo.itemData(index)
        except Exception:
            key = None
        if key:
            self.apply_theme(str(key))
            # Hand the keyboard back to the file grid once the picker is done —
            # but never while the user is still arrow-navigating the open popup.
            try:
                if not self.theme_combo.view().isVisible():
                    self.list_widget.setFocus()
            except Exception:
                pass

    def _on_language_changed(self, index: int):
        """Persist the user's language choice and retranslate the whole UI live."""
        lang = "en" if index == 0 else "fa"
        # Keep the combo in sync when this is called programmatically
        # (tests / screenshot scripts) instead of from the combo itself.
        combo = getattr(self, "lang_combo", None)
        if combo is not None:
            try:
                combo.blockSignals(True)
                combo.setCurrentIndex(index)
                combo.blockSignals(False)
            except Exception:
                pass
        if lang == app_i18n.get_language():
            return
        app_i18n.set_language(lang)
        self.config["language"] = lang
        self._save_config()
        app = QtWidgets.QApplication.instance()
        if app:
            app.setLayoutDirection(RTL if app_i18n.is_rtl() else LTR)
        self._retranslate_ui()
        self.status.setText(t("Ready"))
        # After switching language hand the keyboard back to the file grid
        # (never while the language popup is still being navigated).
        combo = getattr(self, "lang_combo", None)
        if combo is not None:
            try:
                if not combo.view().isVisible():
                    self.list_widget.setFocus()
            except Exception:
                pass

    def _retranslate_ui(self):
        """Update every static text after a language switch (no restart needed)."""
        self.subtitle.setText(t("Fast browsing, previews & safe file transfers"))
        self.lbl_theme.setText(t("Theme"))
        self.lbl_language.setText(t("Language"))
        combo = getattr(self, "theme_combo", None)
        if combo is not None:
            # Theme picker items are translated too (روشن / کاغذی / گرافیتی /
            # تیره / جنگلی / مشکی خالص) — the same idea as the old _theme_key.
            try:
                combo.blockSignals(True)
                for i in range(combo.count()):
                    key = combo.itemData(i)
                    if key in THEMES:
                        combo.setItemText(i, t(THEMES[key].get("label", key)))
            except Exception:
                pass
            finally:
                try:
                    combo.blockSignals(False)
                except Exception:
                    pass
        self.btn_open_ext.setText(t("Open with system player"))
        self.btn_change_folder.setText(t("Change folder"))
        self.btn_refresh.setText(t("Refresh"))
        self.folder_label.setText(self._folder_label_text())
        self.filter_edit.setPlaceholderText(t("Filter: .jpg,.png,.mp4 or empty"))
        self.sort_combo.blockSignals(True)
        self.sort_combo.setItemText(0, t("Name"))
        self.sort_combo.setItemText(1, t("Type"))
        self.sort_combo.blockSignals(False)
        self.lbl_thumb.setText(t("Thumb:"))
        self.stop_btn.setText(t("Stop"))
        self.play_btn.setText(t("Play / Pause"))
        self.lbl_cat.setText(t("Categories"))
        self.quick_lbl.setText(t("Click: move selected files • Right-click: edit / remove / reorder"))
        self.btn_save_set.setText(t("Save set"))
        self.btn_load_set.setText(t("Load set"))
        self.btn_export_set.setText(t("Export"))
        self.btn_import_set.setText(t("Import"))
        self.btn_clear_thumbs.setText(t("Clear thumbnail cache"))
        self.btn_add_quick.setText(t("+ Add Category"))
        self.btn_cancel_all.setText(t("Cancel transfers"))
        self.btn_undo.setText(t("Undo move"))
        self.btn_undo.setToolTip(t("Move the files of the last transfer back to their original folder (Ctrl+Z)"))
        self._update_undo_state()
        try:
            q = len(self.transfer_mgr.queue)
            a = len(self.transfer_mgr.active_futures)
        except Exception:
            q = a = 0
        self.total_files_label.setText(t("Total: {n}").format(n=self.list_widget.count()))
        self.transfer_done_label.setText(t("Done: {n}").format(n=self.transfers_completed))
        self.transfer_failed_label.setText(t("Failed: {n}").format(n=self.transfers_failed))
        self.transfer_queue_label.setText(t("Queued: {n}").format(n=q))
        self.transfer_active_label.setText(t("Active: {n}").format(n=a))
        self.transfer_busy_label.setText(t("Busy: Yes") if (q or a) else t("Busy: No"))
        self._refresh_categories_ui()
        sel_items = self.list_widget.selectedItems()
        if not sel_items:
            self.preview_label.setText(t("Preview"))
        else:
            # Re-render card/image previews so placeholder texts follow the new
            # language instantly (skip while a video is actively playing).
            playing_now = bool(getattr(self, "qt_video", None) and self.qt_video.isVisible()) or self.vlc_frame.isVisible()
            if not playing_now:
                try:
                    self.show_preview(Path(sel_items[0].data(USER_ROLE)))
                except Exception:
                    pass

    def _folder_label_text(self) -> str:
        if not self.candidate_folder:
            return t("No folder selected — click 'Change folder'")
        return str(self.candidate_folder) + (t("  • recursive") if self.include_subfolders else "")

    # ---------------- categories ----------------
    def _category_dialog(self, title: str, cat: Optional[dict] = None):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        form = QtWidgets.QFormLayout(dlg)
        name = QtWidgets.QLineEdit(cat.get("name", "") if cat else "")
        path = QtWidgets.QLineEdit(cat.get("path", "") if cat else "")
        btn = QtWidgets.QPushButton(t("Browse"))
        def _browse_cat_path():
            start = self._browse_start_dir(path.text().strip())
            d = QtWidgets.QFileDialog.getExistingDirectory(self, t("Select"), start)
            if d:
                path.setText(d)
                self._remember_browse_dir(d)
        btn.clicked.connect(_browse_cat_path)
        h = QtWidgets.QHBoxLayout(); h.addWidget(path); h.addWidget(btn)
        form.addRow(t("Name"), name); form.addRow(t("Path"), h)
        buttons = QtWidgets.QDialogButtonBox(OkButton | CancelButton)
        form.addWidget(buttons)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        res = dlg.exec() if QT6 else dlg.exec_()
        if not _is_dialog_accepted(res):
            return None
        n = name.text().strip() or t("Untitled")
        p = path.text().strip()
        if not p:
            QtWidgets.QMessageBox.warning(self, t("Invalid category"), t("Path cannot be empty."))
            return None
        resolved = str(Path(p).expanduser())
        # A relative path (e.g. "Photos") would silently resolve against
        # whatever folder the app was started from and scatter files there.
        # Only absolute paths are accepted; "~" was expanded above.
        if not Path(resolved).is_absolute():
            QtWidgets.QMessageBox.warning(
                self, t("Invalid category"),
                t("Please enter an absolute path (for example {example}).", example="C:\\Users\\you\\Pictures"))
            return None
        self._remember_browse_dir(resolved)
        return {"name": n, "path": resolved}

    def add_category(self):
        cat = self._category_dialog(t("Add Category"))
        if not cat: return
        self.categories.append(cat); self.categories = normalize_categories(self.categories)
        self._save_config(); self._refresh_categories_ui(); self.status.setText(t("Category added"))

    # The context menu of the merged category buttons dispatches here with the
    # button's index; there is no separate list selection any more.
    def edit_category(self, idx: int):
        if not (0 <= idx < len(self.categories)): return
        cat = self._category_dialog(t("Edit Category"), self.categories[idx])
        if not cat: return
        self.categories[idx] = cat; self.categories = normalize_categories(self.categories)
        self._save_config(); self._refresh_categories_ui(); self.status.setText(t("Category edited"))

    def remove_category(self, idx: int):
        if not (0 <= idx < len(self.categories)): return
        del self.categories[idx]
        self._save_config(); self._refresh_categories_ui(); self.status.setText(t("Category removed"))

    def _move_category(self, idx: int, delta: int):
        """Reorder a category by one slot (replaces the old Swap dialog)."""
        j = idx + delta
        if not (0 <= idx < len(self.categories)) or not (0 <= j < len(self.categories)):
            return
        self.categories[idx], self.categories[j] = self.categories[j], self.categories[idx]
        self.categories = normalize_categories(self.categories)
        self._save_config(); self._refresh_categories_ui()
        self.status.setText(t("Category order changed"))

    def _show_category_menu(self, idx: int, btn, pos):
        """Right-click menu of a category button: Edit / Remove / Move up/down."""
        try:
            if not (0 <= idx < len(self.categories)):
                return
            menu = QtWidgets.QMenu(self)
            act_edit = menu.addAction(t("Edit"))
            act_remove = menu.addAction(t("Remove"))
            menu.addSeparator()
            act_up = menu.addAction(t("Move up"))
            act_up.setEnabled(idx > 0)
            act_down = menu.addAction(t("Move down"))
            act_down.setEnabled(idx < len(self.categories) - 1)
            chosen = menu.exec(btn.mapToGlobal(pos))
            if chosen is None:
                return
            if chosen is act_edit:
                self.edit_category(idx)
            elif chosen is act_remove:
                self.remove_category(idx)
            elif chosen is act_up:
                self._move_category(idx, -1)
            elif chosen is act_down:
                self._move_category(idx, +1)
        except Exception:
            traceback.print_exc()

    def save_category_set(self):
        name, ok = QtWidgets.QInputDialog.getText(self, t("Save category set"), t("Set name:"))
        if not ok or not name.strip(): return
        fp = CATEGORY_SETS_DIR / (safe_filename_stem(name.strip()) + ".json")
        try:
            fp.write_text(json.dumps({"name": name.strip(), "categories": normalize_categories(self.categories)}, ensure_ascii=False, indent=2), encoding="utf-8")
            QtWidgets.QMessageBox.information(self, t("Saved"), t("Category set saved: {name}").format(name=fp.name))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, t("Error"), t("Failed to save set: {e}").format(e=e))

    def load_category_set(self):
        sets = sorted(CATEGORY_SETS_DIR.glob("*.json"), key=lambda p: p.name.lower())
        if not sets:
            QtWidgets.QMessageBox.information(self, t("No sets"), t("No saved category sets found.")); return
        items = [p.name for p in sets]
        sel, ok = QtWidgets.QInputDialog.getItem(self, t("Load set"), t("Choose set:"), items, 0, False)
        if not ok or not sel: return
        try:
            j = json.loads((CATEGORY_SETS_DIR / sel).read_text(encoding="utf-8"))
            new_cats = normalize_categories(j.get("categories", []))
            if not new_cats:
                QtWidgets.QMessageBox.warning(self, t("Error"), t("No valid categories in this set.")); return
            mb = QtWidgets.QMessageBox(self); mb.setWindowTitle(t("Load set")); mb.setText(t("Replace existing categories or merge?"))
            replace_btn = mb.addButton(t("Replace"), AcceptRole); merge_btn = mb.addButton(t("Merge"), YesRole); mb.addButton(t("Cancel"), RejectRole)
            mb.exec() if QT6 else mb.exec_()
            clicked = mb.clickedButton()
            if clicked == replace_btn: self.categories = list(new_cats)
            elif clicked == merge_btn: self.categories = normalize_categories(self.categories + new_cats)
            else: return
            self._save_config(); self._refresh_categories_ui(); QtWidgets.QMessageBox.information(self, t("Loaded"), t("Category set loaded."))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, t("Error"), t("Failed to load set: {e}").format(e=e))

    def export_category_set_to_file(self):
        export_start = str(Path(self._browse_start_dir()) / "categories.json") if self._browse_start_dir() else "categories.json"
        fp, _ = QtWidgets.QFileDialog.getSaveFileName(self, t("Export category set"), export_start, "JSON files (*.json);;All files (*)")
        if not fp: return
        try:
            Path(fp).write_text(json.dumps({"name": "export", "categories": normalize_categories(self.categories)}, ensure_ascii=False, indent=2), encoding="utf-8")
            QtWidgets.QMessageBox.information(self, t("Exported"), t("Exported to: {path}").format(path=fp))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, t("Error"), t("Failed to export set: {e}").format(e=e))

    def import_category_set_from_file(self):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, t("Import category set"), self._browse_start_dir(), "JSON files (*.json);;All files (*)")
        if not fp: return
        try:
            j = json.loads(Path(fp).read_text(encoding="utf-8")); new_cats = normalize_categories(j.get("categories", []))
            if not new_cats:
                QtWidgets.QMessageBox.warning(self, t("Error"), t("No valid categories in this file.")); return
            self.categories = normalize_categories(self.categories + new_cats)
            self._save_config(); self._refresh_categories_ui(); QtWidgets.QMessageBox.information(self, t("Imported"), t("Imported {n} categories.").format(n=len(new_cats)))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, t("Error"), t("Failed to import: {e}").format(e=e))

    def _refresh_categories_ui(self):
        self.categories = normalize_categories(self.categories)
        for i in reversed(range(self.quick_layout.count())):
            w = self.quick_layout.itemAt(i).widget()
            if w: w.setParent(None)
        for idx, c in enumerate(self.categories):
            name = c.get("name", "")
            # U+2066/U+2069 isolate the label so the RTL layout of the Persian
            # UI cannot flip a mixed-direction name like "0: Photos" into
            # "Photos :0"; a Persian name still renders naturally. Only the
            # first ten buttons carry the number badge — the digit shortcuts
            # exist just for them, and a "12:" badge would suggest a key that
            # does nothing.
            label = f"\u2066{idx}: {name}\u2069" if idx < 10 else f"\u2066{name}\u2069"
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(c.get("path", ""))
            try:
                btn.setAutoRepeat(False)
            except Exception:
                pass
            btn.clicked.connect(partial(self.move_selected_to_category, idx))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(partial(self._show_category_menu, idx, btn))
            self.quick_layout.addWidget(btn)

    # ---------------- scanning & thumbnails ----------------
    def _make_placeholder_icon(self) -> QIcon:
        pix = QPixmap(self.thumbnail_size, self.thumbnail_size)
        pix.fill(QtGui.QColor("#26334a"))
        return QIcon(pix)

    def _file_type_icon(self, path: Path) -> QIcon:
        key = (path.suffix.lower() or group_for_extension(path.suffix.lower()), int(self.thumbnail_size))
        icon = self._type_icon_cache.get(key)
        if icon is not None:
            return icon
        data = generate_type_card_bytes(str(path), self.thumbnail_size)
        if data:
            pix = QPixmap(); pix.loadFromData(data)
            if not pix.isNull():
                icon = QIcon(pix.scaled(self.thumbnail_size, self.thumbnail_size, KEEP_ASPECT, SMOOTH))
                self._type_icon_cache[key] = icon
                return icon
        icon = self._make_placeholder_icon()
        self._type_icon_cache[key] = icon
        return icon

    def _add_file_item(self, path: Path):
        path_str = str(path)
        if path_str in self.path_to_item: return
        it = QtWidgets.QListWidgetItem()
        it.setData(USER_ROLE, path_str)
        it.setText(path.name)
        tip = f"{path_str}\n{file_size_text(path)}"
        it.setToolTip(tip)
        it.setIcon(self._file_type_icon(path))
        it.setSizeHint(QSize(self.thumbnail_size + 28, self.thumbnail_size + 42))
        self.list_widget.addItem(it)
        self.path_to_item[path_str] = it

    def load_files(self):
        try: self.filter_timer.stop()
        except Exception: pass
        self._scan_generation += 1; self._thumbnail_generation += 1
        scan_id = self._scan_generation
        if not self.candidate_folder:
            try:
                self.populate_timer.stop(); self.visible_thumb_timer.stop(); self.background_thumb_timer.stop()
            except Exception:
                pass
            self.list_widget.clear(); self.path_to_item.clear(); self.thumb_queue.clear(); self._scan_buffer = []
            self._thumb_queued_paths.clear(); self._thumb_processing_paths.clear(); self._thumb_done_paths.clear(); self._background_thumb_index = 0
            self.total_files_label.setText(t("Total: {n}").format(n=0))
            self.progress.setRange(0, 1); self.progress.setValue(0); self.progress.hide()
            self.status.setText(t("Please select a folder first"))
            return
        try:
            if self.scanner and self.scanner.isRunning():
                self.scanner.stop(); self.scanner.wait(500)
        except Exception: pass
        try:
            self.populate_timer.stop()
        except Exception:
            pass
        try:
            self.visible_thumb_timer.stop(); self.background_thumb_timer.stop()
        except Exception:
            pass
        self._populate_files = []
        self._populate_index = 0
        self._background_thumb_index = 0
        self._thumb_queued_paths.clear(); self._thumb_processing_paths.clear(); self._thumb_done_paths.clear()
        self.list_widget.clear(); self.path_to_item.clear(); self.thumb_queue.clear(); self._scan_buffer = []
        self._current_filter_exts = parse_extension_filter(self.filter_edit.text() if hasattr(self, "filter_edit") else "")
        self.total_files_label.setText(t("Total: {n}").format(n=0))
        self.progress.setRange(0, 0)
        self.progress.show()  # indeterminate busy bar while scanning
        self.status.setText(t("Scanning folder..."))
        self.scanner = ScannerThread(scan_id, str(self.candidate_folder), self.include_subfolders)
        self.scanner.file_found.connect(self._on_scanner_file_found)
        self.scanner.scan_done.connect(self._on_scanner_done)
        self.scanner.scan_error.connect(self._on_scanner_error)
        self.scanner.start()

    def _on_scanner_file_found(self, scan_id: int, path_str: str):
        if scan_id != self._scan_generation: return
        try:
            p = Path(path_str)
            if self._current_filter_exts and p.suffix.lower() not in self._current_filter_exts: return
            self._scan_buffer.append(str(p))
            if len(self._scan_buffer) % 100 == 0:
                self.total_files_label.setText(t("Found: {n}").format(n=len(self._scan_buffer)))
        except Exception: traceback.print_exc()

    def _on_scanner_done(self, scan_id: int):
        if scan_id != self._scan_generation: return
        try:
            sort_mode = "Type" if (hasattr(self, "sort_combo") and self.sort_combo.currentIndex() == 1) else "Name"
            files = [Path(s) for s in self._scan_buffer]
            files.sort(key=lambda p: sort_key_for_path(p, sort_mode))
            self._populate_files = files
            self._populate_index = 0
            self.total_files_label.setText(t("Total: {a} / {b}").format(a=0, b=len(files)))
            self.status.setText(t("Scan complete — populating list..."))
            self.populate_timer.start()
        except Exception:
            traceback.print_exc(); self.status.setText(t("Scan failed"))
        finally:
            self._scan_buffer = []
            # Back to the hidden idle state — the bar used to stay full (100%)
            # forever after a scan, which looked like a stuck transfer.
            self.progress.setRange(0, 1); self.progress.setValue(0); self.progress.hide()

    def _populate_next_batch(self):
        try:
            if not self._populate_files:
                self.populate_timer.stop()
                return
            batch = 80
            total = len(self._populate_files)
            end = min(total, self._populate_index + batch)
            self.list_widget.setUpdatesEnabled(False)
            try:
                for p in self._populate_files[self._populate_index:end]:
                    self._add_file_item(p)
            finally:
                self.list_widget.setUpdatesEnabled(True)
            self._populate_index = end
            self.total_files_label.setText(t("Total: {a} / {b}").format(a=self.list_widget.count(), b=total))
            self.visible_thumb_timer.start()
            if end >= total:
                self.populate_timer.stop()
                self._populate_files = []
                self._populate_index = 0
                self.total_files_label.setText(t("Total: {n}").format(n=self.list_widget.count()))
                # A rescan triggered by undo keeps its result message alive:
                # the scan/populate flow would otherwise overwrite "Undone:
                # N file(s) back in the explorer" before anyone can read it.
                pending = getattr(self, "_status_after_rescan", "")
                if pending:
                    self._status_after_rescan = ""
                    self.status.setText(pending)
                else:
                    self.status.setText(t("Ready — visible thumbnails first, rest in background"))
                self.background_thumb_timer.start()
        except Exception:
            traceback.print_exc()
            self.populate_timer.stop()

    def _on_scanner_error(self, scan_id: int, errmsg: str):
        if scan_id != self._scan_generation: return
        self.progress.setRange(0, 1); self.progress.setValue(0); self.progress.hide()
        QtWidgets.QMessageBox.warning(self, t("Scan error"), errmsg); self.status.setText(t("Scan error"))

    def _set_item_icon_from_bytes(self, path_str: str, png_bytes: bytes) -> bool:
        it = self.path_to_item.get(path_str)
        if not it or not png_bytes:
            return False
        pix = QPixmap(); pix.loadFromData(png_bytes)
        if pix.isNull():
            return False
        it.setIcon(QIcon(pix.scaled(self.thumbnail_size, self.thumbnail_size, KEEP_ASPECT, SMOOTH)))
        return True

    def _enqueue_thumbnail(self, path_str: str, priority: bool = False):
        if path_str not in self.path_to_item:
            return
        if path_str in self._thumb_done_paths:
            return
        cached = cached_thumbnail_bytes(path_str, self.thumbnail_size)
        if cached and self._set_item_icon_from_bytes(path_str, cached):
            self._thumb_done_paths.add(path_str)
            self._thumb_queued_paths.discard(path_str)
            return
        item = (self._thumbnail_generation, path_str, self.thumbnail_size)
        if path_str in self._thumb_queued_paths:
            # Re-prioritize visible/selected items even if they were already
            # queued as background. Duplicates are skipped later once done.
            if priority:
                self.thumb_queue.appendleft(item)
            return
        self._thumb_queued_paths.add(path_str)
        if priority:
            self.thumb_queue.appendleft(item)
        else:
            self.thumb_queue.append(item)

    def _visible_row_range(self) -> Tuple[int, int]:
        if self.list_widget.count() <= 0:
            return (0, -1)
        viewport = self.list_widget.viewport()
        top_item = self.list_widget.itemAt(2, 2)
        bottom_item = self.list_widget.itemAt(max(2, viewport.width() - 4), max(2, viewport.height() - 4))
        start = self.list_widget.row(top_item) if top_item else 0
        end = self.list_widget.row(bottom_item) if bottom_item else min(self.list_widget.count() - 1, start + 60)
        if end < start:
            end = start
        return max(0, start), min(self.list_widget.count() - 1, end)

    def _queue_visible_thumbnails(self):
        try:
            if self.list_widget.count() <= 0:
                return
            vis_start, vis_end = self._visible_row_range()
            # 1) visible items: highest priority
            for row in range(vis_start, vis_end + 1):
                it = self.list_widget.item(row)
                if it:
                    self._enqueue_thumbnail(str(it.data(USER_ROLE)), priority=True)
            # 2) near viewport: normal priority (next screens)
            near_start = max(0, vis_start - 30)
            near_end = min(self.list_widget.count() - 1, vis_end + 120)
            for row in range(near_start, near_end + 1):
                if vis_start <= row <= vis_end:
                    continue
                it = self.list_widget.item(row)
                if it:
                    self._enqueue_thumbnail(str(it.data(USER_ROLE)), priority=False)
            # 3) selected items always jump to front
            for it in self.list_widget.selectedItems():
                self._enqueue_thumbnail(str(it.data(USER_ROLE)), priority=True)
        except Exception as e:
            log_exception("queue visible thumbnails failed", e)

    def _queue_background_thumbnails(self):
        try:
            count = self.list_widget.count()
            if count <= 0:
                self.background_thumb_timer.stop()
                return
            vis_start, vis_end = self._visible_row_range()
            queued = 0
            checked = 0
            # Add a small slice per tick so the UI stays responsive. Visible items
            # can still re-prioritize themselves to the front of the queue.
            while checked < 300 and queued < 80 and self._background_thumb_index < count:
                row = self._background_thumb_index
                self._background_thumb_index += 1
                checked += 1
                if vis_start <= row <= vis_end:
                    continue
                it = self.list_widget.item(row)
                if it:
                    self._enqueue_thumbnail(str(it.data(USER_ROLE)), priority=False)
                    queued += 1
            if self._background_thumb_index >= count:
                self.background_thumb_timer.stop()
        except Exception as e:
            log_exception("queue background thumbnails failed", e)

    def _submit_thumb_batch(self):
        try:
            submitted = 0
            while self.thumb_queue and submitted < THUMB_BATCH_SIZE and self._thumb_inflight < THUMB_MAX_INFLIGHT:
                generation, path, req_size = self.thumb_queue.popleft()
                if generation != self._thumbnail_generation or path not in self.path_to_item:
                    self._thumb_queued_paths.discard(path)
                    continue
                if path in self._thumb_done_paths or path in self._thumb_processing_paths:
                    continue
                self._thumb_processing_paths.add(path)
                self._thumb_inflight += 1
                try:
                    self.thumb_executor.submit(self._thumb_task, generation, path, req_size)
                except Exception:
                    self._thumb_inflight = max(0, self._thumb_inflight - 1)
                    self._thumb_processing_paths.discard(path)
                    raise
                submitted += 1
        except RuntimeError:
            pass
        except Exception:
            traceback.print_exc()

    def _thumb_task(self, generation: int, path: str, req_size: int):
        try:
            data = generate_thumbnail_bytes(path, req_size, allow_expensive=True) or b""
            self.thumb_signals.finished.emit(generation, path, data, req_size)
        except Exception:
            traceback.print_exc()
            try: self.thumb_signals.finished.emit(generation, path, b"", req_size)
            except Exception: pass

    def _on_thumb_finished(self, generation: int, path_str: str, png_bytes: bytes, requested_size: int):
        self._thumb_inflight = max(0, self._thumb_inflight - 1)
        self._thumb_queued_paths.discard(path_str)
        self._thumb_processing_paths.discard(path_str)
        if generation != self._thumbnail_generation:
            return
        try:
            it = self.path_to_item.get(path_str)
            if not it: return
            if png_bytes:
                pix = QPixmap(); pix.loadFromData(png_bytes)
                if not pix.isNull():
                    scaled = pix.scaled(self.thumbnail_size, self.thumbnail_size, KEEP_ASPECT, SMOOTH)
                    it.setIcon(QIcon(scaled)); self._thumb_done_paths.add(path_str); return
            provider = QtWidgets.QFileIconProvider(); it.setIcon(provider.icon(QtCore.QFileInfo(path_str)))
        except Exception: traceback.print_exc()

    # ---------------- preview & playback ----------------
    def _stop_external_player(self):
        proc = getattr(self, "external_player_proc", None)
        self.external_player_proc = None
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _launch_external_player(self, path: Path, nodisp: bool = False) -> bool:
        """Fallback playback through bundled ffplay.exe when embedded VLC fails.

        nodisp=True is used for audio files (mp3/wav/...): ffplay then plays
        pure sound without popping up its spectrum window.
        """
        ffplay = bundled_tool("ffplay")
        if not ffplay:
            return False
        try:
            self._stop_external_player()
            # -loop 0: when the clip ends, ffplay restarts it from the
            # beginning (same looping behaviour as the embedded engines).
            cmd = [ffplay, "-hide_banner", "-loglevel", "error"]
            if nodisp:
                cmd.append("-nodisp")
            cmd += ["-autoexit", "-loop", "0", str(path)]
            self.external_player_proc = popen_hidden_subprocess(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(path.parent) if path.parent.exists() else None,
            )
            return True
        except Exception as e:
            log_exception("ffplay fallback failed", e)
            return False

    def _reset_preview(self):
        try:
            if self.preview_movie is not None: self.preview_movie.stop()
            self.preview_movie = None; self._preview_original_pixmap = None
            try:
                if getattr(self, "qt_video", None):
                    self.qt_video.stop()
            except Exception:
                pass
            try:
                self.vlc_frame.stop()
                if getattr(self.vlc_frame, "player", None):
                    try:
                        self.vlc_frame.player.set_media(None)
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop_external_player()
            self._playback_active = False
            self._audio_mode = False
            if getattr(self, "qt_video", None):
                self.qt_video.hide()
            self.vlc_frame.hide(); self.preview_label.show(); self.preview_label.clear(); self.play_btn.setText(t("Play / Pause"))
        except Exception: pass

    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            self._reset_preview(); self.preview_label.setText(t("Preview")); return
        path = Path(items[0].data(USER_ROLE))
        self._enqueue_thumbnail(str(path), priority=True)
        self.show_preview(path)

    def _load_image_pixmap_safely(self, path: Path) -> Optional[QPixmap]:
        try:
            rdr = QImageReader(str(path)); rdr.setAutoTransform(True)
            original = rdr.size()
            if original.isValid() and (original.width() > SAFE_MAX_IMAGE_DIM or original.height() > SAFE_MAX_IMAGE_DIM):
                scaled = original.scaled(QSize(SAFE_MAX_IMAGE_DIM, SAFE_MAX_IMAGE_DIM), KEEP_ASPECT)
                rdr.setScaledSize(scaled)
            img = rdr.read()
            if img and not img.isNull(): return QPixmap.fromImage(img)
        except Exception: pass
        try:
            data = generate_thumbnail_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 680))
            if data:
                pix = QPixmap(); pix.loadFromData(data)
                if not pix.isNull(): return pix
        except Exception: pass
        return None

    def _show_scaled_pixmap(self, pix: Optional[QPixmap]) -> bool:
        if pix and not pix.isNull():
            self._preview_original_pixmap = pix
            self._rescale_preview_pixmap()
            return True
        return False

    def _rescale_preview_pixmap(self):
        if self._preview_original_pixmap and not self._preview_original_pixmap.isNull() and self.preview_label.isVisible():
            self.preview_label.setPixmap(self._preview_original_pixmap.scaled(self.preview_label.size(), KEEP_ASPECT, SMOOTH))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._rescale_preview_pixmap()

    def _start_embedded_video(self, path: Path, engine: str) -> bool:
        """Start playback with one embedded engine ('qt' or 'vlc').

        Returns True when the engine is active; a delayed health check
        (_verify_embedded_video) falls through to the next engine if the
        video surface never materializes.
        """
        if engine == "qt":
            if not getattr(self, "qt_video", None):
                return False
            try:
                self.qt_video.play(str(path))
                self.qt_video.show(); self.preview_label.hide()
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
                self._playback_active = True
                self.play_btn.setText(t("Pause"))
                self.status.setText(t("Playing (embedded player)"))
                QTimer.singleShot(2500, lambda p=str(path): self._verify_embedded_video(p, "qt"))
                return True
            except Exception as e:
                log_exception("Qt video autoplay failed", e)
                self.qt_video.stop(); self.qt_video.hide(); self.preview_label.show()
                return False
        if engine == "vlc":
            if not VLC_AVAILABLE:
                return False
            try:
                self.vlc_frame.show(); self.preview_label.hide()
                try:
                    QtWidgets.QApplication.processEvents()
                except Exception:
                    pass
                self.vlc_frame.play(str(path))
                self._playback_active = True
                self.play_btn.setText(t("Pause"))
                self.status.setText(t("Playing (bundled VLC)"))
                QTimer.singleShot(1800, lambda p=str(path): self._verify_embedded_video(p, "vlc"))
                return True
            except Exception as e:
                log_exception("VLC autoplay failed", e)
                self.vlc_frame.hide(); self.preview_label.show()
                return False
        return False

    def _start_playback_fallbacks(self, path: Path, skip: str = ""):
        """Remaining engines after an embedded one failed: qt -> vlc -> ffplay."""
        for engine in ("qt", "vlc"):
            if engine == skip:
                continue
            if self._start_embedded_video(path, engine):
                return
        if self._launch_external_player(path):
            self._playback_active = True
            self.play_btn.setText(t("Play"))
            self.preview_label.setText(t("Playing with bundled ffplay"))
            self.status.setText(t("Playing with bundled ffplay fallback"))
            return
        reason = self._video_unavailable_status()
        data = (cached_thumbnail_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560))
                or cached_thumbnail_bytes(str(path), self.thumbnail_size)
                or generate_type_card_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560)))
        if data:
            pix = QPixmap(); pix.loadFromData(data)
            if not pix.isNull():
                # A still frame with a play badge communicates "this is a video,
                # but no player engine is available" much better than plain text.
                if self._show_scaled_pixmap(self._pixmap_with_play_overlay(pix)):
                    self.status.setText(reason)
                    return
        self.preview_label.setText(t("Video playback unavailable"))
        self.status.setText(reason)

    def _video_unavailable_status(self) -> str:
        """Bilingual status explaining WHY no video engine is available."""
        if not HAS_QTMEDIA and QTMEDIA_IMPORT_ERROR and not getattr(self, "_logged_qtmedia_error", False):
            self._logged_qtmedia_error = True
            log_exception("Qt Multimedia import failed", RuntimeError(QTMEDIA_IMPORT_ERROR))
        if not HAS_QTMEDIA:
            return t("No video player found — run: pip install -U PyQt6")
        return t("Video playback failed — reinstall SortView (its PyQt6 is broken or outdated)")

    def _show_audio_artwork(self, path: Path) -> bool:
        """Show the audio type card (or cached artwork) while sound plays."""
        data = (cached_thumbnail_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560))
                or cached_thumbnail_bytes(str(path), self.thumbnail_size)
                or generate_type_card_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560)))
        if data:
            pix = QPixmap(); pix.loadFromData(data)
            if not pix.isNull() and self._show_scaled_pixmap(pix):
                return True
        self.preview_label.setText(path.name)
        return False

    def _start_embedded_audio(self, path: Path) -> bool:
        """Audio-only playback through the Qt Multimedia engine.

        QMediaPlayer decodes mp3/wav/flac/… with the FFmpeg backend that
        ships inside the PyQt6/PySide6 wheels — the same engine that plays
        videos — so no extra runtime is needed. The clip loops exactly like
        videos do (setLoops(-1)). No video surface is required, so the audio
        type card stays on screen while the sound plays.
        """
        if not HAS_QTMEDIA or not getattr(self, "qt_video", None):
            return False
        try:
            self._audio_mode = True
            self.qt_video.play(str(path))  # plays audio-only files fine
            self.qt_video.hide(); self.preview_label.show()
            self._playback_active = True
            self.play_btn.setText(t("Pause"))
            self.status.setText(t("Playing audio (embedded player)"))
            self._show_audio_artwork(path)
            return True
        except Exception as e:
            log_exception("Qt audio autoplay failed", e)
            self._audio_mode = False
            try:
                self.qt_video.stop()
            except Exception:
                pass
            self.preview_label.show()
            return False

    def _start_audio_fallbacks(self, path: Path):
        """Remaining audio engines after embedded playback failed."""
        if self._launch_external_player(path, nodisp=True):
            self._playback_active = True
            self.play_btn.setText(t("Play"))
            self.status.setText(t("Playing audio with bundled ffplay"))
            self._show_audio_artwork(path)
            return
        reason = self._video_unavailable_status()
        self._show_audio_artwork(path)
        self.status.setText(reason)

    def _pixmap_with_play_overlay(self, pix: QPixmap) -> QPixmap:
        """Composite a translucent circular play badge onto a still preview."""
        try:
            out = QPixmap(pix)
            painter = QtGui.QPainter(out)
            try:
                rh = getattr(QtGui.QPainter, "RenderHint", None)
                anti = getattr(rh, "Antialiasing", None) if rh is not None else None
                if anti is not None:
                    painter.setRenderHint(anti, True)
                w, h = out.width(), out.height()
                r = max(20.0, min(w, h) * 0.13)
                cx, cy = w / 2.0, h / 2.0
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 190), 2))
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 150)))
                painter.drawEllipse(QtCore.QPointF(cx, cy), r, r)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 235)))
                painter.setPen(QtGui.QPen(QtCore.Qt.PenStyle.NoPen))
                tri_w, tri_h = r * 0.7, r * 0.8
                path = QtGui.QPainterPath()
                path.moveTo(cx - tri_w / 2.0 + tri_w * 0.15, cy - tri_h / 2.0)
                path.lineTo(cx - tri_w / 2.0 + tri_w * 0.15, cy + tri_h / 2.0)
                path.lineTo(cx + tri_w / 2.0 + tri_w * 0.15, cy)
                path.closeSubpath()
                painter.drawPath(path)
            finally:
                painter.end()
            return out
        except Exception:
            return pix

    def _confirm_run_executable(self, path: Path) -> bool:
        """Shared safety net for every 'open outside the app' path.

        Double-click (open_file) and the system-player button must behave
        identically: launching a program-like file (.exe/.bat/.ps1/…) from a
        folder the app merely browses has to be an explicit bilingual yes/no
        decision. Returns True when the open may proceed.
        """
        try:
            if path.suffix.lower() not in self.EXECUTABLE_OPEN_EXTS:
                return True
            answer = QtWidgets.QMessageBox.question(
                self,
                t("Run this file?"),
                t("This file looks like a program ({name}). Open it anyway?").format(name=path.name),
                MsgBox_Yes | MsgBox_No,
                MsgBox_No,  # the safe answer is the default (Enter says No)
            )
            if _enum_int(answer) != _enum_int(MsgBox_Yes):
                self.status.setText(t("Opening cancelled"))
                return False
            return True
        except Exception:
            return True

    def open_selected_with_system_player(self):
        """Open the selected file with the default Windows app (no embedded player needed)."""
        try:
            items = self.list_widget.selectedItems()
            if not items:
                self.status.setText(t("No files selected"))
                return
            path = Path(items[0].data(USER_ROLE))
            # Same program-launch guard as double-click: this button used to
            # bypass the executable warning entirely.
            if not self._confirm_run_executable(path):
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            self.status.setText(t("Opened with the system player"))
        except Exception as e:
            self.status.setText(t("Cannot open: {e}").format(e=e))

    def _verify_embedded_video(self, path_str: str, engine: str):
        try:
            item = self.list_widget.currentItem()
            if not item or str(item.data(USER_ROLE)) != path_str:
                return
            if engine == "qt":
                ok = bool(getattr(self, "qt_video", None) and self.qt_video.isVisible() and self.qt_video.has_video_frame())
            else:
                ok = bool(self.vlc_frame.isVisible() and self.vlc_frame.player and self.vlc_frame.has_video_frame())
            if ok:
                return
            # Some systems play audio but fail to attach the video surface (or
            # the decoder errors out). Stop this engine and try the others.
            if engine == "qt" and getattr(self, "qt_video", None):
                self.qt_video.stop(); self.qt_video.hide()
            else:
                self.vlc_frame.stop(); self.vlc_frame.hide()
            self.preview_label.show()
            self._start_playback_fallbacks(Path(path_str), skip=engine)
        except Exception as e:
            log_exception("verify embedded video failed", e)

    def show_preview(self, path: Path):
        self._reset_preview()
        ext = path.suffix.lower()
        if _plays_as_video(path):
            # Auto-play on selection, as requested. Embedded engines are tried
            # first — Qt Multimedia (no external runtime), then libVLC — and
            # bundled ffplay is the last resort. Thumbnail workers continue
            # with low-priority ffmpeg processes so playback stays responsive.
            if self._start_embedded_video(path, "qt") or self._start_embedded_video(path, "vlc"):
                return
            self._start_playback_fallbacks(path)
            return
        if ext in AUDIO_EXTS:
            # Audio files (mp3/wav/flac/…) play like videos but without a
            # video surface: the type card stays visible while sound plays.
            if self._start_embedded_audio(path):
                return
            self._start_audio_fallbacks(path)
            return
        if ext in IMAGE_EXTS:
            if self._show_scaled_pixmap(self._load_image_pixmap_safely(path)): return
            self.preview_label.setText(t("Cannot preview image")); return
        if ext in ANIM_EXTS:
            try:
                movie = QMovie(str(path))
                if movie.isValid():
                    movie.setScaledSize(self.preview_label.size())
                    self.preview_movie = movie; self.preview_label.setMovie(movie); movie.start(); return
            except Exception: traceback.print_exc()
            self.preview_label.setText(t("Cannot preview GIF")); return
        data = (cached_thumbnail_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560))
                or cached_thumbnail_bytes(str(path), self.thumbnail_size)
                or generate_type_card_bytes(str(path), max(self.thumbnail_size * HIGH_PREVIEW_MULT, 560)))
        if data:
            pix = QPixmap(); pix.loadFromData(data)
            if self._show_scaled_pixmap(pix): return
        provider = QtWidgets.QFileIconProvider(); pix = provider.icon(QtCore.QFileInfo(str(path))).pixmap(256, 256)
        if self._show_scaled_pixmap(pix): return
        self.preview_label.setText(path.name)

    def _sync_playback_button(self):
        """Sync the Play/Pause button with the real engine state.

        Without this the label froze at "Pause" after a clip finished or
        looped, so pressing it restarted the video — the classic
        "pause actually replays" confusion reported by users.
        """
        try:
            playing = None
            if getattr(self, "_audio_mode", False) and getattr(self, "qt_video", None) is not None:
                # Audio-only playback: the video surface stays hidden, so the
                # visibility checks below would never fire. Watch the player
                # state directly instead.
                try:
                    playing = (MEDIA_PLAYING is not None
                               and _enum_int(self.qt_video.player.playbackState()) == _enum_int(MEDIA_PLAYING))
                except Exception:
                    playing = None
            elif getattr(self, "qt_video", None) is not None and self.qt_video.isVisible():
                try:
                    playing = (MEDIA_PLAYING is not None
                               and _enum_int(self.qt_video.player.playbackState()) == _enum_int(MEDIA_PLAYING))
                except Exception:
                    playing = None
            elif VLC_AVAILABLE and getattr(self.vlc_frame, "player", None) and self.vlc_frame.isVisible():
                try:
                    playing = self.vlc_frame.player.get_state() == vlc.State.Playing
                except Exception:
                    playing = None
            if playing is None:
                return  # nothing embedded on screen (external ffplay / no file)
            desired = t("Pause") if playing else t("Play")
            if self.play_btn.text() != desired:
                self.play_btn.setText(desired)
            self._playback_active = bool(playing)
        except Exception:
            pass

    def _play_or_pause(self):
        try:
            items = self.list_widget.selectedItems()
            if not items: return
            path = Path(items[0].data(USER_ROLE))
            ext = path.suffix.lower()
            if ext not in AUDIO_EXTS and not _plays_as_video(path): return
            is_audio = ext in AUDIO_EXTS
            # Audio already loaded in the Qt engine (video surface hidden).
            if is_audio and getattr(self, "_audio_mode", False) and getattr(self, "qt_video", None):
                if getattr(self.qt_video, "_failed", False):
                    # Decoder refused this file — hand it to the next engine.
                    self._audio_mode = False
                    try:
                        self.qt_video.stop()
                    except Exception:
                        pass
                    self._start_audio_fallbacks(path)
                    return
                playing = self.qt_video.pause_or_resume()
                self._playback_active = bool(playing)
                self.play_btn.setText(t("Pause") if playing else t("Play"))
                return
            if getattr(self, "qt_video", None) and self.qt_video.isVisible():
                try:
                    playing = self.qt_video.pause_or_resume()
                    self._playback_active = bool(playing)
                    self.play_btn.setText(t("Pause") if playing else t("Play"))
                    return
                except Exception as e:
                    log_exception("Qt play/pause failed", e)
                    self.qt_video.stop(); self.qt_video.hide(); self.preview_label.show()
            if VLC_AVAILABLE and self.vlc_frame.player and self.vlc_frame.isVisible():
                try:
                    playing = self.vlc_frame.pause_or_resume()
                    self._playback_active = bool(playing)
                    self.play_btn.setText(t("Pause") if playing else t("Play"))
                    return
                except Exception as e:
                    log_exception("VLC play/pause failed", e)
                    self.vlc_frame.hide(); self.preview_label.show()
            # Nothing is playing yet — stop any external ffplay first so two
            # players never overlap, then start an embedded engine, then ffplay.
            self._stop_external_player()
            if is_audio:
                if self._start_embedded_audio(path):
                    return
                self._start_audio_fallbacks(path)
                return
            if self._start_embedded_video(path, "qt") or self._start_embedded_video(path, "vlc"):
                return
            if self._launch_external_player(path):
                self._playback_active = True
                self.play_btn.setText(t("Play"))
                self.status.setText(t("Playing with bundled ffplay fallback"))
            else:
                self._playback_active = False
                self.status.setText(t("No bundled player is available"))
        except Exception: traceback.print_exc()

    def _stop_video(self):
        try:
            self._audio_mode = False
            if getattr(self, "qt_video", None):
                self.qt_video.stop(); self.qt_video.hide()
            self.vlc_frame.stop(); self._stop_external_player(); self._playback_active = False; self.play_btn.setText(t("Play"))
        except Exception: traceback.print_exc()

    # ---------------- moving files ----------------
    def _on_transfer_started(self, src: str, dst_dir: str):
        it = self.path_to_item.get(src)
        if it: it.setBackground(QtGui.QColor("#fff5cc"))
        self.status.setText(t("Moving {name}...").format(name=Path(src).name))

    def move_selected_to_category(self, idx: int):
        items = self.list_widget.selectedItems()
        if not items:
            self.status.setText(t("No files selected")); return
        if not (0 <= idx < len(self.categories)):
            self.status.setText(t("Invalid category index")); return
        # One-shot: ignore hold/repeat and ignore a second press while delay is pending.
        now = time.monotonic()
        last = getattr(self, "_last_move_request_ts", 0.0)
        if (now - last) < 0.30:
            return
        if getattr(self, "_move_enqueue_pending", False):
            return
        self._last_move_request_ts = now
        dst = str(Path(self.categories[idx].get("path", "")).expanduser())
        if not dst:
            self.status.setText(t("Category path is empty")); return
        current_sel = str(Path(items[0].data(USER_ROLE))) if items else None
        # Snapshot selection now — selection may change during the short VLC release delay.
        src_list = []
        for it in items:
            try:
                src_list.append(str(Path(it.data(USER_ROLE))))
            except Exception:
                pass
        if not src_list:
            self.status.setText(t("No files selected")); return
        # Stop preview/playback before moving; on Windows VLC can lock the selected video.
        # player.stop() is asynchronous — give libVLC a moment to release the file handle
        # before rename/move, otherwise the native renderer can crash the whole process.
        try:
            self._reset_preview()
        except Exception:
            pass
        self._last_transfer_initiator_preview = current_sel
        self._move_enqueue_pending = True
        self.status.setText(t("Preparing transfer..."))
        QTimer.singleShot(200, lambda: self._do_enqueue_transfers(src_list, dst))

    def _do_enqueue_transfers(self, src_list, dst: str):
        """Actually queue file moves after preview/VLC has released handles."""
        try:
            # Extra safety: ensure VLC is fully stopped right before disk ops.
            try:
                self.vlc_frame.stop()
            except Exception:
                pass
            try:
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass
            queued = 0
            skipped = 0
            for src in src_list:
                try:
                    if same_path(Path(src).parent, Path(dst)):
                        skipped += 1
                        continue
                except Exception:
                    pass
                it = self.path_to_item.get(src)
                if self.transfer_mgr.enqueue(src, dst):
                    queued += 1
                    if it is not None:
                        try:
                            it.setBackground(QtGui.QColor("#fff5cc"))
                        except Exception:
                            pass
                else:
                    skipped += 1
            if queued:
                msg = t("Queued {n} transfer(s)").format(n=queued)
                if skipped:
                    msg += t(", skipped {n}").format(n=skipped)
                self.status.setText(msg)
                self.btn_cancel_all.show()
                # Open a new undo batch for this transfer round. If another
                # round is still in flight, its batch stays open and the two
                # rounds merge into one undo entry (all files return, which
                # is always safe).
                if not self._undo_batch_open:
                    self._undo_batch_open = True
                    self._undo_pending = []
                    self._undo_expected = 0
                    self._undo_done = 0
                # Every file enqueued while the batch is open must report back
                # (finished or error) before the batch may be sealed.
                self._undo_expected += queued
            elif skipped:
                self.status.setText(t("No new files queued"))
            else:
                self.status.setText(t("No files queued"))
        except Exception:
            traceback.print_exc()
        finally:
            self._move_enqueue_pending = False

    def _on_transfer_finished(self, src: str, newpath: str):
        try:
            self.transfers_completed += 1; self.transfer_done_label.setText(t("Done: {n}").format(n=self.transfers_completed))
            # Record the completed move for the open undo batch: the pair
            # (original source, final destination) is exactly what undo needs
            # to put the file back (also restoring the original name after
            # an auto-rename like "name (1).ext").
            if self._undo_batch_open:
                self._undo_pending.append((src, newpath))
                self._undo_done += 1
            it = self.path_to_item.pop(src, None)
            current_preview = None
            sel = self.list_widget.currentItem()
            if sel: current_preview = str(sel.data(USER_ROLE))
            if it:
                row = self.list_widget.row(it); self.list_widget.takeItem(row)
                self.total_files_label.setText(t("Total: {n}").format(n=self.list_widget.count()))
                if current_preview == src or self._last_transfer_initiator_preview == src:
                    cnt = self.list_widget.count()
                    if cnt > 0: self.list_widget.setCurrentRow(min(row, cnt - 1))
                    else: self.on_selection_changed()
            self._last_transfer_initiator_preview = None
            self.status.setText(t("Moved as {name}").format(name=Path(newpath).name) if Path(newpath).name != Path(src).name else t("Transfer finished"))
        except Exception: traceback.print_exc()

    def _on_transfer_error(self, src: str, errmsg: str):
        try:
            self.transfers_failed += 1; self.transfer_failed_label.setText(t("Failed: {n}").format(n=self.transfers_failed))
            it = self.path_to_item.get(src)
            if it: it.setBackground(QtGui.QColor("#ffdddd"))
            self.status.setText(t("Error moving {name}: {err}").format(name=Path(src).name, err=errmsg))
            # A failed/cancelled file has nothing to undo, but it HAS reported
            # back — without this the batch would never reach done == expected.
            if self._undo_batch_open:
                self._undo_done += 1
        except Exception: traceback.print_exc()

    def _on_transfer_queue_updated(self, queued: int, active: int):
        self.transfer_active_label.setText(t("Active: {n}").format(n=active))
        self.transfer_queue_label.setText(t("Queued: {n}").format(n=queued))
        self.transfer_busy_label.setText(t("Busy: Yes") if active or queued else t("Busy: No"))
        self.btn_cancel_all.setVisible(bool(active or queued))
        if not queued and not active:
            # The queue just drained — seal the open undo batch so the next
            # Ctrl+Z refers exactly to the transfer round that finished.
            # Race guard: a (0, 0) can also be emitted by the manager's tick
            # between the worker popping the last future and the UI processing
            # that file's transfer_finished event. Only seal when every file
            # this batch expected has actually reported back.
            if self._undo_batch_open and self._undo_done >= self._undo_expected:
                self._close_undo_batch()

    def _cancel_all_transfers(self):
        # Files dropped from the queue were never started, so they will never
        # report back — remove them from the batch's expected count, otherwise
        # the undo batch could never be sealed again.
        dropped = self.transfer_mgr.cancel_all()
        if self._undo_batch_open:
            self._undo_expected = max(0, self._undo_expected - int(dropped or 0))
            # cancel_all() already emitted queue_updated(0, 0) — synchronously,
            # BEFORE the expected count was fixed up above — so that run of the
            # close-check correctly saw done < expected and refused to seal.
            # If nothing is running any more, no further signal will ever arrive
            # and the batch would stay open (with the Undo button disabled) until
            # the next round merges it. Re-run the seal check now that the
            # counters are consistent. When futures were still running, is_idle()
            # is False here and their own finished/error events close the batch.
            if self.transfer_mgr.is_idle() and self._undo_done >= self._undo_expected:
                self._close_undo_batch()
        self.status.setText(t("Cancellation requested for transfers"))

    # ---------------- undo of transfers ----------------
    def _update_undo_state(self):
        try:
            self.btn_undo.setEnabled(bool(self._undo_stack) and not self._undo_active)
        except Exception:
            pass

    def _close_undo_batch(self):
        """Seal the open undo batch once the transfer queue has drained."""
        try:
            if not self._undo_batch_open:
                return
            self._undo_batch_open = False
            if self._undo_pending:
                self._undo_stack.append(self._undo_pending)
                self._undo_pending = []
                self._update_undo_state()
        except Exception:
            traceback.print_exc()

    def _undo_last_move(self):
        """Move the files of the last transfer round back to their folders."""
        try:
            fw = QtWidgets.QApplication.focusWidget()
            # Text fields handle Ctrl+Z themselves (undoing the typed text) —
            # the same guard as the digit shortcuts.
            if isinstance(fw, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QSpinBox)):
                return
            if self._undo_active:
                return
            if not self._undo_stack:
                self.status.setText(t("Nothing to undo"))
                return
            batch = self._undo_stack.pop()
            self._undo_active = True
            self._update_undo_state()
            # Release any preview handle first (VLC can lock a file on Windows).
            try:
                self._reset_preview()
            except Exception:
                pass
            self.status.setText(t("Undoing last move..."))
            threading.Thread(target=self._undo_worker, args=(batch,), daemon=True).start()
        except Exception:
            self._undo_active = False
            self._update_undo_state()
            traceback.print_exc()

    def _undo_worker(self, batch):
        """Worker thread: move every (source, destination) pair back. Never
        overwrites anything — if the original slot is taken again, the file
        is restored beside it under a unique name.

        Reports three lists: restored pairs, pairs that failed for a
        possibly temporary reason (e.g. a file locked by another program),
        and pairs whose file has left the category folder (gone — nothing
        to restore, never retried)."""
        restored, failed, gone = [], [], []
        try:
            for src, dst in batch:
                try:
                    dst_p = Path(dst)
                    src_p = Path(src)
                    if not dst_p.is_file():
                        # The file is no longer in the category folder — the
                        # user moved it by hand; nothing to restore.
                        gone.append((src, dst))
                        continue
                    src_p.parent.mkdir(parents=True, exist_ok=True)
                    target = src_p
                    if target.exists():
                        target = unique_destination(src_p, None)
                    try:
                        shutil.move(str(dst_p), str(target))
                    except PermissionError:
                        # A read-only file cannot be deleted after the
                        # cross-drive copy inside shutil.move; copy it back
                        # explicitly and remove the read-only source.
                        shutil.copy2(str(dst_p), str(target))
                        force_unlink(dst_p)
                    restored.append((src, str(target)))
                except Exception:
                    failed.append((src, dst))
        finally:
            self.undo_signals.finished.emit(restored, failed, gone)

    def _on_undo_finished(self, restored, failed, gone):
        try:
            self._undo_active = False
            if failed:
                # Re-queue only pairs whose file is still in the category
                # folder (a real, possibly temporary failure such as a file
                # locked by another program). Pairs whose file is gone would
                # fail forever — re-appending them used to jam the whole
                # undo stack so older rounds never became reachable again.
                retry = [(s, d) for (s, d) in failed if Path(d).is_file()]
                if retry:
                    self._undo_stack.append(retry)
            n, m, g = len(restored), len(failed), len(gone)
            if n and m:
                msg = t("Undone: {n} file(s) restored, {m} kept in the category folder").format(n=n, m=m)
            elif n and g:
                msg = t("Undone: {n} file(s) back in the explorer, {m} had already been moved by hand").format(n=n, m=g)
            elif n:
                msg = t("Undone: {n} file(s) back in the explorer").format(n=n)
            elif m:
                msg = t("Nothing was restored — the files are still in the category folder")
            elif g:
                msg = t("Nothing was restored — the files are no longer in the category folder")
            else:
                msg = ""
            # Rescan the folder so the restored files reappear in the grid.
            # The summary message is kept and shown once the rescan finishes.
            self._status_after_rescan = msg
            self.load_files()
            self._update_undo_state()
        except Exception:
            traceback.print_exc()

    def clear_thumbnail_cache(self):
        try:
            mb = QtWidgets.QMessageBox(self)
            mb.setWindowTitle(t("Clear thumbnails"))
            mb.setText(t("Clear the thumbnail cache? Thumbnails will be regenerated in the background afterwards."))
            clear_btn = mb.addButton(t("Clear"), AcceptRole)
            mb.addButton(t("Cancel"), RejectRole)
            mb.exec() if QT6 else mb.exec_()
            if mb.clickedButton() != clear_btn:
                return
            self._thumbnail_generation += 1
            self.thumb_queue.clear()
            self._thumb_queued_paths.clear()
            self._thumb_processing_paths.clear()
            self._thumb_done_paths.clear()
            self._background_thumb_index = 0
            deleted = 0
            total_size = 0
            THUMB_CACHE.mkdir(parents=True, exist_ok=True)
            for fp in list(THUMB_CACHE.glob("*")):
                try:
                    if fp.is_file():
                        total_size += fp.stat().st_size
                        fp.unlink()
                        deleted += 1
                except Exception:
                    pass
            self.status.setText(t("Thumbnail cache cleared: {n} files, {mb} MB").format(n=deleted, mb=f"{total_size / (1024*1024):.1f}"))
            self.load_files()
        except Exception as e:
            traceback.print_exc()
            self.status.setText(t("Cannot clear thumbnail cache: {e}").format(e=e))

    # ---------------- folder/open/close ----------------
    def change_folder(self):
        dlg = QtWidgets.QDialog(self); dlg.setWindowTitle(t("Select folder"))
        dlg.setMinimumWidth(500)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.setSpacing(10)
        # First launch: empty (no path). Later: last candidate folder, else last browse dir.
        start_dir = self._browse_start_dir(
            str(self.candidate_folder) if self.candidate_folder else ""
        )
        form = QtWidgets.QHBoxLayout(); le = QtWidgets.QLineEdit(start_dir); browse = QtWidgets.QPushButton(t("Browse"))
        def on_browse():
            d = QtWidgets.QFileDialog.getExistingDirectory(
                self, t("Select folder"), le.text().strip() or self._browse_start_dir()
            )
            if d:
                le.setText(d)
                self._remember_browse_dir(d)
        browse.clicked.connect(on_browse); form.addWidget(le); form.addWidget(browse); layout.addLayout(form)
        # The recursive option gets its own highlighted card. A bare checkbox
        # row was too easy to miss — users did not realize it was clickable.
        card = QtWidgets.QFrame(); card.setObjectName("CheckCard")
        card_l = QtWidgets.QVBoxLayout(card)
        card_l.setContentsMargins(14, 12, 14, 12); card_l.setSpacing(7)
        chk = QtWidgets.QCheckBox(t("Include files from subfolders (recursive)"))
        chk.setObjectName("BigCheck"); chk.setChecked(bool(self.include_subfolders))
        try:
            chk.setCursor(_qt_value(Qt, "CursorShape", "PointingHandCursor", default=13))
        except Exception:
            pass
        hint = QtWidgets.QLabel(t("Checked: files inside all subfolders are listed too. Unchecked: only the files of this folder."))
        hint.setObjectName("CheckHint"); hint.setWordWrap(True)
        card_l.addWidget(chk); card_l.addWidget(hint)
        layout.addWidget(card)
        buttons = QtWidgets.QDialogButtonBox(OkButton | CancelButton); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); layout.addWidget(buttons)
        res = dlg.exec() if QT6 else dlg.exec_()
        if _is_dialog_accepted(res):
            d = le.text().strip()
            if d:
                new_folder = Path(d).expanduser()
                if not new_folder.exists() or not new_folder.is_dir():
                    QtWidgets.QMessageBox.warning(self, t("Invalid folder"), t("Selected path is not a folder.")); return
                try:
                    if self.scanner and self.scanner.isRunning(): self.scanner.stop(); self.scanner.wait(500)
                except Exception: pass
                self.candidate_folder = new_folder; self._folder_user_selected = True; self.include_subfolders = bool(chk.isChecked())
                self._remember_browse_dir(str(new_folder))
                self.folder_label.setText(self._folder_label_text()); self._save_config(); self.load_files()

    EXECUTABLE_OPEN_EXTS = {
        ".exe", ".bat", ".cmd", ".com", ".scr", ".ps1", ".msi", ".lnk",
        ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".jar",
        ".url", ".reg", ".pif", ".chm", ".cpl", ".msc", ".docm", ".xlsm",
        ".py", ".pyw",
    }

    def open_file(self, item):
        try:
            path = Path(item.data(USER_ROLE))
            # Safety net: the app browses unknown folders, so double-clicking
            # a program should be an explicit decision (bilingual warning).
            # Shared with the system-player button so both stay in sync.
            if not self._confirm_run_executable(path):
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except Exception as e:
            self.status.setText(t("Cannot open: {e}").format(e=e))

    def closeEvent(self, ev):
        try:
            if self.scanner and self.scanner.isRunning(): self.scanner.stop(); self.scanner.wait(800)
        except Exception: pass
        try: self.populate_timer.stop(); self.background_thumb_timer.stop(); self.visible_thumb_timer.stop()
        except Exception: pass
        try: self.thumb_submit_timer.stop()
        except Exception: pass
        try: self.thumb_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError: self.thumb_executor.shutdown(wait=False)
        except Exception: pass
        try: self.transfer_mgr.shutdown()
        except Exception: pass
        try: self._stop_external_player()
        except Exception: pass
        try: self.vlc_frame.cleanup()
        except Exception: pass
        try:
            if getattr(self, "qt_video", None):
                self.qt_video.cleanup()
        except Exception: pass
        self._save_config(); super().closeEvent(ev)

    # ---------------- helpers ----------------
    def _on_thumb_slider_changed(self, val: int):
        try:
            self._pending_thumb_size = int(val); self.thumb_size_label.setText(str(val)); self.thumb_apply_timer.start()
        except Exception: pass

    def _apply_pending_thumb_size(self):
        try:
            val = int(self._pending_thumb_size)
            if val != self.thumbnail_size:
                self.thumbnail_size = val; self._save_config(); self.list_widget.setIconSize(QSize(self.thumbnail_size, self.thumbnail_size)); self.thumb_queue.clear(); self.load_files()
        except Exception: traceback.print_exc()

    def _on_key_shortcut(self, k: int):
        try:
            fw = QtWidgets.QApplication.focusWidget()
            # QComboBox is included so typing digits while the theme/language
            # picker has focus navigates the combo instead of moving files.
            if isinstance(fw, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QSpinBox, QtWidgets.QComboBox)):
                return
            # Extra guard: ignore rapid re-triggers while a move is already being prepared.
            now = time.monotonic()
            last = getattr(self, "_last_key_shortcut_ts", 0.0)
            if (now - last) < 0.25:
                return
            self._last_key_shortcut_ts = now
            if k < len(self.categories): self.move_selected_to_category(k)
            else: QtWidgets.QMessageBox.information(self, t("No category"), t("No category assigned to {k}").format(k=k))
        except Exception: traceback.print_exc()


# ---------------- main ----------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    try:  # one startup note for support: which Qt binding actually loaded
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] started "
                    f"(Qt binding: {QT_API}, Python {sys.version.split()[0]})\n")
    except Exception:
        pass
    app.setLayoutDirection(RTL if app_i18n.is_rtl() else LTR)
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    if APP_FONT.exists():
        try:
            fid = QtGui.QFontDatabase.addApplicationFont(str(APP_FONT))
            fams = QtGui.QFontDatabase.applicationFontFamilies(fid)
            if fams:
                app.setFont(QtGui.QFont(fams[0], 10))
        except Exception:
            pass
    w = SortView()
    w.show()
    sys.exit(app.exec() if QT6 else app.exec_())


if __name__ == "__main__":
    main()
