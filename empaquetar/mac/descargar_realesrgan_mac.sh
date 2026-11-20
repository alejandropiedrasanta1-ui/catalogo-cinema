#!/bin/bash
# Descarga el ejecutable oficial de Real-ESRGAN ncnn Vulkan para macOS (BSD-3, xinntao/Real-ESRGAN, v0.2.5.0)
# en <carpeta>/realesrgan-ncnn-vulkan. Los modelos ya vienen en el repositorio (recursos/realesrgan/models).
set -euo pipefail
DEST="$1"
EXE="$DEST/realesrgan-ncnn-vulkan"
if [ -x "$EXE" ]; then echo "Real-ESRGAN para Mac ya está"; exit 0; fi
URL="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip"
TMP="$(mktemp -d)"
curl -fsSL "$URL" -o "$TMP/r.zip"
unzip -q "$TMP/r.zip" -d "$TMP/r"
ENC=$(find "$TMP/r" -type f -name "realesrgan-ncnn-vulkan" | head -1)
cp "$ENC" "$EXE"
chmod +x "$EXE"
xattr -c "$EXE" 2>/dev/null || true
rm -rf "$TMP"
echo "Real-ESRGAN para Mac listo: $EXE"
