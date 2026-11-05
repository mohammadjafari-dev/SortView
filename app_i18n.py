#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Part of SortView (سورت‌ویو).
# Copyright (C) 2026 Mohammad Jafari (mohammadjafari-dev)
# SPDX-License-Identifier: GPL-3.0-or-later
"""
app_i18n — tiny bilingual (English / Persian) translation layer for
SortView (سورت‌ویو).

Design goals:
  * zero dependencies (no Qt import here — safe to use from worker threads)
  * canonical strings are the English texts; Persian comes from the FA table
  * startup language: saved user choice (config.json -> "language") wins,
    otherwise the OS display language is auto-detected
  * the user's choice is persisted by the app via config.json and survives
    restarts
"""
from __future__ import annotations

import json
import locale
import os
from typing import Dict, Optional, Tuple

LANGUAGES: Tuple[Tuple[str, str], ...] = (("en", "English"), ("fa", "فارسی"))
RTL_LANGS = {"fa"}
SUPPORTED = {lang for lang, _ in LANGUAGES}

_current: str = "en"

# ---------------------------------------------------------------------------
# Persian table. Keys are the canonical English strings used in the UI.
# "{x}" placeholders must be kept intact — they are filled with .format().
# ---------------------------------------------------------------------------
FA: Dict[str, str] = {
    # --- header / main window ---
    "Fast browsing, previews & safe file transfers": "مرور سریع، پیش‌نمایش و انتقال امن فایل‌ها",
    "Theme:": "تم:",
    "Language:": "زبان:",
    "Theme": "تم",
    "Language": "زبان",
    # --- theme names on the theme picker ---
    "Dark": "تیره",
    "Light": "روشن",
    "Paper": "کاغذی",
    "Graphite": "گرافیتی",
    "Forest": "جنگلی",
    "AMOLED": "مشکی خالص",
    # --- left panel ---
    "Change folder": "تغییر پوشه",
    "Refresh": "بازخوانی",
    "No folder selected — click 'Change folder'": "هیچ پوشه‌ای انتخاب نشده — روی تغییر پوشه کلیک کن",
    "  • recursive": "  • زیرپوشه‌ها هم",
    "Filter: .jpg,.png,.mp4 or empty": "فیلتر: .jpg,.png,.mp4 یا خالی",
    "Name": "نام",
    "Type": "نوع",
    "Thumb:": "تامبنیل:",
    # --- preview panel ---
    "Preview": "پیش‌نمایش",
    "Play / Pause": "پخش / توقف موقت",
    "Play": "پخش",
    "Pause": "توقف موقت",
    "Stop": "توقف",
    "Playing (bundled VLC)": "در حال پخش (VLC همراه برنامه)",
    "Embedded video failed; playing with bundled ffplay": "پخش داخلی ناموفق بود؛ پخش با ffplay همراه برنامه",
    "Playing with bundled ffplay": "در حال پخش با ffplay همراه برنامه",
    "Playing with bundled ffplay fallback": "پخش با ffplay جایگزین",
    "Video playback failed": "پخش ویدیو ناموفق بود",
    "Video playback failed; see user_data/app.log": "پخش ویدیو ناموفق بود؛ لاگ را در user_data/app.log ببین",
    "Video preview only — no player available": "فقط پیش‌نمایش ویدیو — پخش‌کننده‌ای موجود نیست",
    "Video playback unavailable": "پخش ویدیو در دسترس نیست",
    "No bundled player is available": "هیچ پخش‌کننده‌ای همراه برنامه موجود نیست",
    "No video player found — run: pip install -U PyQt6": "هیچ پخش‌کننده‌ای پیدا نشد — اجرا کن: pip install -U PyQt6",
    "Video playback failed — reinstall SortView (its PyQt6 is broken or outdated)": "پخش ویدیو ناموفق بود — SortView را دوباره نصب کن (PyQt6 برنامه خراب یا قدیمی است)",
    "Open with system player": "پخش با برنامه‌ی خود سیستم",
    "Open the selected file with the default Windows app": "باز کردن فایل انتخاب‌شده با برنامه‌ی پیش‌فرض ویندوز",
    "Opened with the system player": "با برنامه‌ی خود سیستم باز شد",
    "Playing (embedded player)": "در حال پخش (پخش‌کننده‌ی داخلی)",
    "Playing audio (embedded player)": "در حال پخش صدا (پخش‌کننده‌ی داخلی)",
    "Playing audio with bundled ffplay": "پخش صدا با ffplay همراه برنامه",
    "Run this file?": "اجرای این فایل؟",
    "This file looks like a program ({name}). Open it anyway?": "این فایل شبیه یک برنامه است ({name}). با این حال باز شود؟",
    "Opening cancelled": "باز کردن لغو شد",
    "Cannot preview image": "پیش‌نمایش عکس ممکن نیست",
    "Cannot preview GIF": "پیش‌نمایش GIF ممکن نیست",
    # --- right panel ---
    "Categories": "دسته‌ها",
    "Edit": "ویرایش",
    "Remove": "حذف",
    "Save set": "ذخیره مجموعه",
    "Load set": "بارگذاری مجموعه",
    "Export": "برون‌بری",
    "Import": "درون‌ریزی",
    "Click: move selected files • Right-click: edit / remove / reorder": "کلیک: انتقال فایل‌های انتخابی • راست‌کلیک: ویرایش / حذف / جابه‌جایی",
    "Clear thumbnail cache": "پاک کردن کش تامبنیل‌ها",
    "Ready": "آماده",
    "Cancel transfers": "لغو انتقال‌ها",
    "+ Add Category": "+ افزودن دسته",
    # --- status bar ---
    "Total: {n}": "کل: {n}",
    "Found: {n}": "پیدا شده: {n}",
    "Busy: Yes": "مشغول: بله",
    "Busy: No": "مشغول: خیر",
    "Done: {n}": "انجام‌شده: {n}",
    "Queued: {n}": "در صف: {n}",
    "Failed: {n}": "ناموفق: {n}",
    "Active: {n}": "فعال: {n}",
    # --- category dialog ---
    "Browse": "مرور...",
    "Select": "انتخاب پوشه",
    "Select folder": "انتخاب پوشه",
    "Path": "مسیر",
    "Untitled": "بدون نام",
    "Invalid category": "دسته نامعتبر",
    "Path cannot be empty.": "مسیر نمی‌تواند خالی باشد.",
    "Please enter an absolute path (for example {example}).": "لطفاً یک مسیر کامل وارد کنید (مثلاً {example}).",
    "Add Category": "افزودن دسته",
    "Edit Category": "ویرایش دسته",
    "Category added": "دسته اضافه شد",
    "Category edited": "دسته ویرایش شد",
    "Category removed": "دسته حذف شد",
    "Category order changed": "ترتیب دسته‌ها عوض شد",
    "Move up": "جابه‌جایی به بالا",
    "Move down": "جابه‌جایی به پایین",
    # --- category sets ---
    "Save category set": "ذخیره مجموعه دسته‌ها",
    "Set name:": "نام مجموعه:",
    "Saved": "ذخیره شد",
    "Category set saved: {name}": "مجموعه دسته‌ها ذخیره شد: {name}",
    "Error": "خطا",
    "Failed to save set: {e}": "ذخیره مجموعه ناموفق بود: {e}",
    "No sets": "مجموعه‌ای وجود ندارد",
    "No saved category sets found.": "هیچ مجموعه دسته‌ای ذخیره نشده است.",
    "Load set": "بارگذاری مجموعه",
    "Choose set:": "انتخاب مجموعه:",
    "No valid categories in this set.": "دسته معتبری در این مجموعه نیست.",
    "Replace existing categories or merge?": "دسته‌های فعلی جایگزین شوند یا ادغام شوند؟",
    "Replace": "جایگزینی",
    "Merge": "ادغام",
    "Cancel": "انصراف",
    "Loaded": "بارگذاری شد",
    "Category set loaded.": "مجموعه دسته‌ها بارگذاری شد.",
    "Failed to load set: {e}": "بارگذاری مجموعه ناموفق بود: {e}",
    "Export category set": "برون‌بری مجموعه دسته‌ها",
    "Exported": "برون‌بری شد",
    "Exported to: {path}": "برون‌بری شد به: {path}",
    "Failed to export set: {e}": "برون‌بری مجموعه ناموفق بود: {e}",
    "Import category set": "درون‌ریزی مجموعه دسته‌ها",
    "No valid categories in this file.": "دسته معتبری در این فایل نیست.",
    "Imported": "درون‌ریزی شد",
    "Imported {n} categories.": "{n} دسته درون‌ریزی شد.",
    "Failed to import: {e}": "درون‌ریزی ناموفق بود: {e}",
    # --- scanning / list ---
    "Please select a folder first": "لطفاً اول یک پوشه انتخاب کن",
    "Scanning folder...": "در حال اسکن پوشه...",
    "Scan complete — populating list...": "اسکن کامل شد — در حال ساخت لیست...",
    "Scan failed": "اسکن ناموفق بود",
    "Scan error": "خطای اسکن",
    "Folder does not exist or is not a directory": "پوشه وجود ندارد یا مسیر انتخاب‌شده پوشه نیست",
    "Ready — visible thumbnails first, rest in background": "آماده — اول تامبنیل‌های نمایان، بقیه در پس‌زمینه",
    "Total: {a} / {b}": "کل: {a} / {b}",
    # --- moving files ---
    "Moving {name}...": "در حال انتقال {name}...",
    "No files selected": "فایلی انتخاب نشده",
    "Invalid category index": "اندیس دسته نامعتبر است",
    "Category path is empty": "مسیر دسته خالی است",
    "Preparing transfer...": "در حال آماده‌سازی انتقال...",
    "Queued {n} transfer(s)": "{n} انتقال در صف قرار گرفت",
    ", skipped {n}": "، {n} مورد رد شد",
    "No new files queued": "فایل جدیدی در صف قرار نگرفت",
    "No files queued": "فایلی در صف قرار نگرفت",
    "Moved as {name}": "منتقل شد با نام {name}",
    "Transfer finished": "انتقال تمام شد",
    "Error moving {name}: {err}": "خطا در انتقال {name}: {err}",
    "Cancellation requested for transfers": "درخواست لغو انتقال‌ها ثبت شد",
    "Cancelled": "لغو شد",
    "Source file does not exist": "فایل مبدأ وجود ندارد",
    "File is already in the destination folder": "فایل از قبل در پوشه مقصد است",
    "Copy size mismatch — the original file was kept": "حجم نسخه‌ی کپی‌شده با مبدأ نمی‌خواند — فایل مبدأ حذف نشد",
    # --- undo of transfers ---
    "Undo move": "برگرداندن انتقال",
    "Move the files of the last transfer back to their original folder (Ctrl+Z)": "فایل‌های آخرین انتقال را به پوشه‌ی قبلی‌شان برمی‌گرداند (Ctrl+Z)",
    "Nothing to undo": "چیزی برای برگرداندن نیست",
    "Undoing last move...": "در حال برگرداندن آخرین انتقال...",
    "Undone: {n} file(s) back in the explorer": "برگشت: {n} فایل به اکسپلورر برگشت",
    "Undone: {n} file(s) restored, {m} kept in the category folder": "برگشت: {n} فایل بازگشت، {m} مورد در پوشه‌ی دسته ماند",
    "Undone: {n} file(s) back in the explorer, {m} had already been moved by hand": "برگشت: {n} فایل به اکسپلورر برگشت، {m} مورد قبلاً دستی جابه‌جا شده بود",
    "Nothing was restored — the files are still in the category folder": "چیزی برگردانده نشد — فایل‌ها هنوز در پوشه‌ی دسته هستند",
    "Nothing was restored — the files are no longer in the category folder": "چیزی برگردانده نشد — فایل‌ها دیگر در پوشه‌ی دسته نیستند",
    # --- thumbnail cache ---
    "Clear thumbnails": "پاک‌سازی تامبنیل‌ها",
    "Clear the thumbnail cache? Thumbnails will be regenerated in the background afterwards.": "کش تامبنیل‌ها پاک شود؟ بعد از پاک کردن، تامبنیل‌ها دوباره در پس‌زمینه ساخته می‌شوند.",
    "Clear": "پاک کردن",
    "Thumbnail cache cleared: {n} files, {mb} MB": "کش تامبنیل پاک شد: {n} فایل، {mb} مگابایت",
    "Cannot clear thumbnail cache: {e}": "پاک‌سازی کش تامبنیل ممکن نیست: {e}",
    # --- folder dialog / misc ---
    "Include files from subfolders (recursive)": "شامل فایل‌های زیرپوشه‌ها (بازگشتی)",
    "Checked: files inside all subfolders are listed too. Unchecked: only the files of this folder.": "با تیک: فایل‌های داخل همه‌ی زیرپوشه‌ها هم لیست می‌شوند. بدون تیک: فقط فایل‌های خود همین پوشه.",
    "Invalid folder": "پوشه نامعتبر",
    "Selected path is not a folder.": "مسیر انتخاب‌شده پوشه نیست.",
    "Cannot open: {e}": "باز کردن ممکن نیست: {e}",
    "No category": "بدون دسته",
    "No category assigned to {k}": "به کلید {k} دسته‌ای اختصاص داده نشده است",
    # --- language switch notice ---
    "Language changed.": "زبان تغییر کرد.",
}


def _detect_system_language() -> str:
    """Best-effort OS display language detection without Qt."""
    candidates = []
    try:  # Windows: user's default ANSI/UTF locale like fa_IR
        loc = locale.getdefaultlocale()[0]
        if loc:
            candidates.append(loc)
    except Exception:
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):  # Unix-style
        val = os.environ.get(var, "")
        if val:
            candidates.append(val)
            break
    for item in candidates:
        try:
            if str(item).lower().startswith("fa"):
                return "fa"
        except Exception:
            continue
    return "en"


def qt_system_language() -> str:
    """Qt-based detection (more reliable on Windows); returns 'fa' or 'en'."""
    try:
        from PyQt6 import QtCore  # noqa
        name = QtCore.QLocale.system().name()  # e.g. 'fa_IR'
    except Exception:
        try:
            from PySide6 import QtCore  # noqa
            name = QtCore.QLocale.system().name()
        except Exception:
            return _detect_system_language()
    return "fa" if str(name).lower().startswith("fa") else "en"


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in SUPPORTED else "en"


def get_language() -> str:
    return _current


def is_rtl(lang: Optional[str] = None) -> bool:
    return (lang or _current) in RTL_LANGS


def language_label(lang: str) -> str:
    for code, label in LANGUAGES:
        if code == lang:
            return label
    return lang


def t(key: str, **kwargs) -> str:
    """Translate `key` into the current language; format with kwargs if given."""
    text = key
    if _current != "en":
        text = FA.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text


def load_saved_language(config_path, qt_hint: bool = True) -> str:
    """Read the persisted user choice; fall back to the system language."""
    saved = ""
    try:
        p = str(config_path)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                saved = str(data.get("language", "") or "").strip().lower()
    except Exception:
        saved = ""
    lang = saved if saved in SUPPORTED else (qt_system_language() if qt_hint else _detect_system_language())
    set_language(lang)
    return lang
