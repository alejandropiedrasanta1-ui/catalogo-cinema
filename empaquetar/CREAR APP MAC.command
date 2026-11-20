#!/bin/bash
# Crea en CATAGOLO COMPLETO/INSTALADOR el instalador de Mac (ventana nativa, un clic):
#   "Instalar Catalogo Cinema (Mac Apple Silicon) <versión>.dmg"
# Uso en la Mac: abre Terminal, escribe  bash  (con un espacio), arrastra este archivo y pulsa Enter.
# (Normalmente no hace falta: GitHub Actions lo crea solo en cada cambio.)
set -e
cd "$(dirname "$0")"
RAIZ="$(cd .. && pwd)"

if ! command -v swiftc >/dev/null 2>&1; then
  echo "Faltan las herramientas de Apple. Escribe en Terminal:  xcode-select --install  y vuelve a ejecutar este archivo."
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Falta Python 3. Instálalo desde https://www.python.org/downloads/macos/ y vuelve a ejecutar este archivo."
  exit 1
fi

echo "[1/4] Preparando entorno de Python (solo la primera vez tarda)..."
VENV="$HOME/Library/Caches/catalogo-cinema-venv"
python3 -m venv "$VENV"
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet PySide6 PySide6-Fluent-Widgets Pillow pyinstaller dmgbuild

echo "[2/4] Ampliador IA para Mac (Real-ESRGAN, solo la primera vez)..."
bash mac/descargar_realesrgan_mac.sh "$RAIZ/recursos/realesrgan"

echo "[3/4] Empaquetando la app..."
python -m PyInstaller --noconfirm --clean --distpath dist-mac --workpath build-mac catalogo.spec

echo "[4/4] Creando el instalador de un clic..."
SALIDA="$(cd "$RAIZ/.." && pwd)/INSTALADOR"
DMG=$(PYTHON=python bash crear_instalador_mac.sh "$PWD/dist-mac/Catalogo Cinema.app" "$SALIDA")
rm -rf dist-mac build-mac

echo
echo "Listo: $DMG"
echo "Para instalar: abre el .dmg y haz doble clic en «Instalar Catálogo»."
