#!/usr/bin/env bash
# One-time install, run by a helper. Idempotent: safe to run again.
#
#   curl -fsSL https://raw.githubusercontent.com/MarcoArmenta/OneButton/main/bootstrap/install.sh | bash
#
# or, from a clone:  bash bootstrap/install.sh
set -euo pipefail

REPO_URL="${ONEBUTTON_REPO:-https://github.com/MarcoArmenta/OneButton.git}"
DEST="${ONEBUTTON_HOME:-$HOME/OneButton}"

say() { printf '\n==> %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null || die "git no está instalado. En macOS: xcode-select --install. En Debian/Ubuntu: sudo apt install git"
command -v python3 >/dev/null || die "python3 no está instalado."
command -v claude >/dev/null || die "Claude Code no está instalado. Ver https://docs.anthropic.com/claude-code e inicia sesión una vez con: claude"

if [ ! -d "$DEST/.git" ]; then
  say "Clonando $REPO_URL en $DEST"
  git clone --quiet "$REPO_URL" "$DEST"
fi
cd "$DEST"
git remote set-url origin "$REPO_URL"
git fetch --tags --quiet origin

say "Creando entorno de Python"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

say "Preparando carpetas locales"
mkdir -p local workspace
[ -f local/config.yaml ] || cp config.example.yaml local/config.yaml
[ -f local/allowed_signers ] || cp bootstrap/allowed_signers local/allowed_signers
cp claude/CLAUDE.md workspace/CLAUDE.md
git config gpg.ssh.allowedSignersFile "$DEST/local/allowed_signers"

if grep -Eq '^[^#[:space:]].*ssh-(ed25519|rsa|ecdsa)' local/allowed_signers; then
  say "Buscando la versión firmada más reciente"
  LATEST="$(git tag --list 'v*' | sort -V | tail -1 || true)"
  if [ -n "$LATEST" ] && git tag -v "$LATEST" >/dev/null 2>&1; then
    git checkout --quiet "$LATEST"
    printf '{"current": "%s", "previous": null}\n' "$LATEST" > local/state.json
    say "Instalada $LATEST"
  else
    say "No hay una versión firmada todavía; se queda en main."
  fi
else
  say "AVISO: local/allowed_signers no tiene una llave real. Las actualizaciones por voz no funcionarán hasta que la tenga."
fi

say "Prueba de voz"
.venv/bin/python - <<'PY'
from onebutton.config import load
from onebutton.tts import Speaker
Speaker(load()).say("OneButton instalado correctamente.")
PY

cat <<MSG

Listo. Para arrancar:   $DEST/bin/onebutton
Para arrancar solo al encender la computadora, ver docs/guia-ayudante.md.
Edita $DEST/local/config.yaml si hace falta cambiar idioma, pausa o voz.
MSG
