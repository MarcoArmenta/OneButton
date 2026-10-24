# OneButton one-time install for Windows. Run by a helper, once. Safe to run again.
#
#   irm https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.ps1 | iex
#
# or from a clone:  powershell -ExecutionPolicy Bypass -File bootstrap\install.ps1
#
# Needs: Git for Windows, Python 3.10+ (python.org, with "Add to PATH"), and
# Claude Code already installed and logged in once.

$ErrorActionPreference = "Stop"
$RepoUrl = if ($env:ONEBUTTON_REPO) { $env:ONEBUTTON_REPO } else { "https://github.com/MarcoArmenta/OneButton.git" }
$Dest    = if ($env:ONEBUTTON_HOME) { $env:ONEBUTTON_HOME } else { Join-Path $env:USERPROFILE "OneButton" }

function Say($m) { Write-Host "`n==> $m" }
function Die($m) { Write-Host "`nERROR: $m" -ForegroundColor Red; exit 1 }
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

if (-not (Have git))    { Die "Falta Git. Instala Git for Windows desde https://git-scm.com/download/win y vuelve a ejecutar." }

# On a fresh Windows 11, "python" is a Microsoft Store stub that opens the Store instead of failing.
# Find a real interpreter: the py launcher first, then python, and demand a version string.
$PythonExe = $null
foreach ($cand in @(@{exe="py"; args=@("-3")}, @{exe="python"; args=@()}, @{exe="python3"; args=@()})) {
  if (-not (Have $cand.exe)) { continue }
  try {
    $v = & $cand.exe @($cand.args) --version 2>&1
    if ("$v" -match "^Python 3\.(\d+)" -and [int]$Matches[1] -ge 10) { $PythonExe = $cand; break }
  } catch {}
}
if (-not $PythonExe) { Die "Falta Python 3.10 o más nuevo. Instala desde https://www.python.org/downloads/ marcando 'Add python.exe to PATH', cierra esta ventana y abre otra." }
if (-not (Have claude)) { Die "No encuentro Claude Code en el PATH. Abre una terminal nueva y escribe 'claude' para comprobarlo." }
if (-not (Have ssh-keygen)) {
  Write-Host "AVISO: falta ssh-keygen (Cliente OpenSSH). Las actualizaciones firmadas no funcionarán hasta activarlo en Configuración > Aplicaciones > Características opcionales." -ForegroundColor Yellow
}

if (-not (Test-Path (Join-Path $Dest ".git"))) {
  Say "Clonando $RepoUrl en $Dest"
  git clone --quiet $RepoUrl $Dest
}
Set-Location $Dest
git remote set-url origin $RepoUrl
git fetch --tags --quiet origin

Say "Creando entorno de Python"
if (-not (Test-Path ".venv")) { & $PythonExe.exe @($PythonExe.args) -m venv .venv }
$Py = Join-Path $Dest ".venv\Scripts\python.exe"
& $Py -m pip install --quiet --upgrade pip
& $Py -m pip install --quiet -r requirements.txt

Say "Descargando el modelo de voz (una sola vez, puede tardar unos minutos)"
& $Py -c "import yaml,pathlib; cfg=yaml.safe_load(open('config.example.yaml')) or {}; p=pathlib.Path('local/config.yaml'); cfg.update(yaml.safe_load(p.read_text()) or {}) if p.exists() else None; from faster_whisper import WhisperModel; WhisperModel(cfg.get('whisper_model','small'), device='cpu', compute_type='int8'); print('modelo listo')"

Say "Preparando carpetas locales"
New-Item -ItemType Directory -Force -Path local, workspace | Out-Null
if (-not (Test-Path "local\config.yaml"))     { Copy-Item config.example.yaml local\config.yaml }
if (-not (Test-Path "local\allowed_signers")) { Copy-Item bootstrap\allowed_signers local\allowed_signers }
$env:ONEBUTTON_HOME = $Dest
& $Py -c "from onebutton.rules import install; from onebutton.config import load; install(list(load().get('modules') or []))"
git config gpg.ssh.allowedSignersFile (Join-Path $Dest "local\allowed_signers")

$hasKey = Select-String -Path "local\allowed_signers" -Pattern '^[^#\s].*ssh-(ed25519|rsa|ecdsa)' -Quiet
if ($hasKey -and (Have ssh-keygen)) {
  Say "Buscando la versión firmada más reciente"
  $latest = (git tag --list 'v*' | Sort-Object { [version]($_.TrimStart('v')) } | Select-Object -Last 1)
  if ($latest) {
    git -c gpg.format=ssh -c gpg.ssh.program=ssh-keygen tag -v $latest 2>$null
    if ($LASTEXITCODE -eq 0) {
      git checkout --quiet $latest
      "{`"current`": `"$latest`", `"previous`": null}" | Set-Content -Encoding UTF8 local\state.json
      Say "Instalada $latest"
    } else { Say "La versión $latest no tiene una firma válida; se queda en main." }
  } else { Say "No hay una versión firmada todavía; se queda en main." }
} else {
  Write-Host "AVISO: local\allowed_signers no tiene una llave real. Las actualizaciones por voz no funcionarán hasta que la tenga." -ForegroundColor Yellow
}

Say "Accesos directos (Escritorio e Inicio automático)"
$Cmd = Join-Path $Dest "bin\onebutton.cmd"
$Shell = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Startup"))) {
  $lnk = $Shell.CreateShortcut((Join-Path $dir "OneButton.lnk"))
  $lnk.TargetPath = $Cmd
  $lnk.WorkingDirectory = $Dest
  $lnk.Description = "OneButton"
  $lnk.Save()
}

Say "Prueba de voz"
& $Py -c "from onebutton.config import load; from onebutton.tts import Speaker; Speaker(load()).say('OneButton instalado correctamente.')"

Write-Host @"

Listo. Para arrancar: doble clic en 'OneButton' en el Escritorio, o $Cmd
Arrancará solo al encender la computadora (carpeta Inicio). Para quitarlo, borra OneButton.lnk de shell:startup.
Ajustes en $Dest\local\config.yaml (idioma, pausa, voz, botón).
"@
