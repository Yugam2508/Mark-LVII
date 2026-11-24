<#
  JARVIS one-step installer for Windows 10/11.

  Run it in PowerShell (no admin needed; winget may ask for permission while
  installing Git or Python):

      powershell -ExecutionPolicy Bypass -File install-windows.ps1

  or, without downloading anything first:

      irm https://raw.githubusercontent.com/Yugam2508/Mark-LVII/main/install-windows.ps1 | iex

  What it does, in order:
    1. Installs Git and Python 3.12 with winget if they are missing.
    2. Downloads JARVIS to %USERPROFILE%\Jarvis (or updates it if already there).
    3. Creates a private Python environment in Jarvis\.venv and runs setup.py in it.
    4. Puts a J.A.R.V.I.S. shortcut on the desktop.
    5. Optionally installs Tailscale, so your phone can reach JARVIS away from home.

  Running it again is safe: it updates the code and the packages and keeps your
  settings, keys and memory (they live in files git does not track).
#>
param(
    [string]$Repo = "https://github.com/Yugam2508/Mark-LVII.git",
    [string]$Branch = "main",
    [string]$Dir = "$env:USERPROFILE\Jarvis",
    [switch]$WithTailscale
)

$ErrorActionPreference = "Stop"

function Say($text)  { Write-Host "`n>> $text" -ForegroundColor Cyan }
# throw, not exit: under "irm ... | iex" an exit would close the user's PowerShell window.
function Fail($text) { Write-Host "`nX  $text" -ForegroundColor Red; throw "JARVIS install stopped." }

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Install-WithWinget($id, $name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "winget is not available. Install '$name' yourself, then run this again."
    }
    Say "Installing $name"
    winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Fail "Installing $name failed (winget exit code $LASTEXITCODE)." }
    Refresh-Path
}

function Find-Python312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        # Windows PowerShell 5.1 turns a redirected native stderr line into a
        # terminating error under "Stop", so the probe runs under "Continue".
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try {
            $p = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $p) { return "$p".Trim() }
        } catch { } finally { $ErrorActionPreference = $old }
    }
    $default = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    if (Test-Path $default) { return $default }
    return $null
}

# ── 1. Git and Python ─────────────────────────────────────────────────────────
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Install-WithWinget "Git.Git" "Git"
}
$python = Find-Python312
if (-not $python) {
    Install-WithWinget "Python.Python.3.12" "Python 3.12"
    $python = Find-Python312
    if (-not $python) { Fail "Python 3.12 was installed but cannot be found. Restart PowerShell and run this again." }
}
Say "Using Python at $python"

# ── 2. Code ───────────────────────────────────────────────────────────────────
if (Test-Path "$Dir\.git") {
    Say "Updating JARVIS in $Dir"
    git -C $Dir fetch origin $Branch
    if ($LASTEXITCODE -ne 0) { Fail "Could not reach GitHub to update." }
    git -C $Dir checkout $Branch
    git -C $Dir pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) {
        Fail "Your copy has local changes that conflict with the update. Ask for help before forcing it."
    }
} elseif (Test-Path $Dir) {
    Fail "$Dir already exists and is not a JARVIS download. Move it, or run with -Dir <another folder>."
} else {
    Say "Downloading JARVIS to $Dir"
    git clone --branch $Branch $Repo $Dir
    if ($LASTEXITCODE -ne 0) { Fail "Download failed. Check the internet connection and the repository address." }
}

# ── 3. Python environment and packages ────────────────────────────────────────
$venvPy = "$Dir\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Say "Creating a private Python environment"
    & $python -m venv "$Dir\.venv"
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python environment." }
}
Say "Installing packages (this takes a few minutes the first time)"
Push-Location $Dir
try {
    & $venvPy -m pip install --upgrade pip
    & $venvPy setup.py
    if ($LASTEXITCODE -ne 0) { Fail "setup.py reported a problem; scroll up for the first error." }
} finally {
    Pop-Location
}

# ── 4. Desktop shortcut ───────────────────────────────────────────────────────
Say "Creating the desktop shortcut"
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("$desktop\J.A.R.V.I.S.lnk")   # same name the app itself uses
$lnk.TargetPath = "$Dir\.venv\Scripts\pythonw.exe"
$lnk.Arguments = "`"$Dir\main.py`""
$lnk.WorkingDirectory = $Dir
if (Test-Path "$Dir\config\jarvis.ico") { $lnk.IconLocation = "$Dir\config\jarvis.ico" }
$lnk.Save()

# ── 5. Tailscale (optional) ───────────────────────────────────────────────────
if (-not $WithTailscale) {
    $answer = Read-Host "`nInstall Tailscale so your phone can use JARVIS away from home? (y/N)"
    $WithTailscale = $answer -match '^(y|yes)$'
}
if ($WithTailscale) {
    if (Get-Command tailscale -ErrorAction SilentlyContinue) {
        Say "Tailscale is already installed"
    } else {
        Install-WithWinget "Tailscale.Tailscale" "Tailscale"
    }
    Write-Host "   Open Tailscale from the Start menu and sign in (use the same account on your phone)."
}

# ── Done ──────────────────────────────────────────────────────────────────────
$gpu = Get-Command nvidia-smi -ErrorAction SilentlyContinue
Write-Host "`n==============================================================" -ForegroundColor Green
Write-Host " JARVIS is installed in $Dir" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host " Start it from the J.A.R.V.I.S. shortcut on your desktop."
Write-Host " First launch asks for your free Gemini key (aistudio.google.com/app/apikey)."
Write-Host " Then: ⚙ -> PLUGIN SETTINGS to connect Google, Spotify and device sync."
if ($gpu) {
    Write-Host " NVIDIA GPU found: in ⚙ -> ENGINE & PROVIDERS you can run speech"
    Write-Host " recognition on the GPU, and local models through Ollama."
}
Write-Host " To update later, run this same script again."
