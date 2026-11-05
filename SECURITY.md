# Security Policy

## Supported versions

Only the **latest release** (see the
[Releases page](../../releases/latest)) receives security fixes. Please
always test against the newest `SortView-win64-portable.zip` before
reporting.

## Reporting a vulnerability

Please do **not** open a public issue for anything that looks like a
security problem (for example: a way to launch files without the
confirmation dialog, path traversal in the category/move logic, or a
malicious archive escaping the thumbnail sandbox).

Use GitHub's **Private vulnerability reporting** instead:
**Security → Report a vulnerability** on this repository. Include the
SortView version, the steps to reproduce, and — if possible — a sample
file or archive that triggers the problem.

You will get an answer within a few days. Fixes land in the next regular
release; there is no separate patched fork.

## What is in scope

- The packaged Windows app (`SortView.exe` and everything inside
  `SortView-win64-portable.zip`).
- The bundled runtime's integration: ffmpeg as invoked by `main.py`
  (list arguments only, never a shell).

## Out of scope

- Vulnerabilities in the bundled upstream binaries themselves — please
  report those to the FFmpeg project, then tell us so we can pin the
  fixed version.
- Social engineering users into running untrusted executables. SortView
  already asks for confirmation before opening program-like files, but a
  user who confirms an explicit warning is outside the threat model.

---

# سیاست امنیتی

فقط **آخرین نسخه‌ی منتشرشده** پشتیبانی می‌شود. لطفاً مشکل امنیتی را با
گزارش‌دهی **خصوصی** گیت‌هاب (تب Security → Report a vulnerability) اعلام
کنید، نه در Issue عمومی. نسخه‌ی برنامه، مراحل بازتولید و در صورت امکان
فایل نمونه را همراه گزارش بفرستید.
