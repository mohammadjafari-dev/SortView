param(
    [Parameter(Mandatory=$true)] [string] $Staging
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Make sure TLS 1.2 is available for downloads on Windows PowerShell 5.1.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch { }

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Staging = Join-Path $Root $Staging
$Downloads = Join-Path $Root 'build\_downloads'
$Bin = Join-Path $Root 'bin'

New-Item -ItemType Directory -Force -Path $Staging | Out-Null
New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
# bin\ is gitignored, so it does not exist on a fresh clone. Create it up
# front: the ffmpeg copy further down writes into it, and with
# $ErrorActionPreference = 'Stop' a missing target folder would abort the
# whole staging step (BUILD.bat reports "Runtime dependency staging
# failed") before the dedicated New-Item below ever runs.
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

# ---------------------------------------------------------------------------
# Pinned tool version + official SHA-256 hash.
#
# Since v1.10.3 ffmpeg is the ONLY runtime binary downloaded here:
#   - video and audio playback run on the Qt Multimedia engine that ships
#     inside the PyQt6 wheels (FFmpeg backend included) — no VLC runtime;
#   - archive thumbnails run on py7zr / stdlib zipfile / tarfile — no 7za.exe;
#   - ffprobe.exe had no caller at all and ffplay.exe was a fallback of a
#     fallback, so both are gone.
# The downloaded artifact is verified against the hash recorded here BEFORE
# it is extracted or copied into the portable package, so a compromised
# mirror or a tampered download can never reach SortView-win64-portable.zip.
#
# To update the tool: change the URL below and record the SHA-256 of the
# official artifact (compute it yourself with Get-FileHash / sha256sum).
# ---------------------------------------------------------------------------
$FfmpegUrl        = 'https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-essentials_build.zip'
$FfmpegSha256     = '04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4'

function Download-File([string]$Url, [string]$OutFile) {
    Write-Host "Downloading $Url"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
    } catch {
        Write-Host "Invoke-WebRequest failed; trying .NET WebClient..."
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($Url, $OutFile)
    }
}

function Assert-FileHash([string]$Path, [string]$ExpectedSha256) {
    # Fail closed: no hash verification, no packaging.
    if ([string]::IsNullOrWhiteSpace($ExpectedSha256)) {
        throw "No expected SHA-256 recorded for $Path - refusing to use it."
    }
    Write-Host "Verifying SHA-256 of $(Split-Path -Leaf $Path)..."
    $actual = (Get-FileHash -Path $Path -Algorithm SHA256).Hash
    if ($actual -ine $ExpectedSha256) {
        throw ("SHA-256 MISMATCH for {0}`n  expected: {1}`n  actual:   {2}`nThe download did not match the pinned official artifact. Delete the file and retry on a trusted network." -f $Path, $ExpectedSha256, $actual)
    }
    Write-Host '  hash OK.'
}

Write-Host '--- Bundling ffmpeg (pinned, hash-verified) ---'
$ffmpegDst = Join-Path $Staging 'ffmpeg.exe'

# Reproducible builds: the ffmpeg in the portable package must always be the
# exact pinned release below — the system-PATH ffmpeg is deliberately NOT
# used, because its version (and license text) would vary from machine to
# machine. The pinned zip is cached in build\_downloads, so repeat builds
# work offline; only a fresh clone needs internet once.
$ffZip = Join-Path $Downloads 'ffmpeg-7.1.1-essentials_build.zip'
$ffDir = Join-Path $Downloads 'ffmpeg'
if (!(Test-Path $ffZip)) {
    Download-File $FfmpegUrl $ffZip
}
# Re-verify even when the file was cached from a previous run.
Assert-FileHash $ffZip $FfmpegSha256
if (Test-Path $ffDir) { Remove-Item $ffDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $ffDir | Out-Null
Expand-Archive -Path $ffZip -DestinationPath $ffDir -Force
$ffmpegFound = Get-ChildItem $ffDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if ($ffmpegFound) {
    Copy-Item $ffmpegFound.FullName $ffmpegDst -Force
    Copy-Item $ffmpegFound.FullName (Join-Path $Bin 'ffmpeg.exe') -Force
}

# GPL compliance: the license text that came inside the pinned ffmpeg zip is
# shipped next to the exe, so SortView-win64-portable.zip carries it too.
# NOTE: inside the zip the file is named `LICENSE` with NO extension, so the
# filter must be 'LICENSE*' (NOT 'LICENSE*.txt' - that never matches and the
# license would silently be left out of the distributed package).
$ffLic = Get-ChildItem $ffDir -Recurse -Filter 'LICENSE*' | Select-Object -First 1
if ($ffLic) {
    Copy-Item $ffLic.FullName (Join-Path $Staging 'ffmpeg-LICENSE.txt') -Force
    Copy-Item $ffLic.FullName (Join-Path $Bin 'ffmpeg-LICENSE.txt') -Force
    Write-Host '  ffmpeg-LICENSE.txt staged.'
} else {
    throw 'ffmpeg LICENSE not found inside the pinned zip - refusing to package without it (GPL compliance).'
}
$ffRdm = Get-ChildItem $ffDir -Recurse -Filter 'README*' | Select-Object -First 1
if ($ffRdm) {
    Copy-Item $ffRdm.FullName (Join-Path $Staging 'ffmpeg-README.txt') -Force
    Copy-Item $ffRdm.FullName (Join-Path $Bin 'ffmpeg-README.txt') -Force
    Write-Host '  ffmpeg-README.txt staged.'
} else {
    throw 'ffmpeg README not found inside the pinned zip - refusing to package without it.'
}

if (!(Test-Path $ffmpegDst)) { throw 'Could not bundle ffmpeg.exe' }
Write-Host 'ffmpeg bundled (pinned 7.1.1, hash verified).'

Write-Host 'Portable runtime staging complete:' $Staging