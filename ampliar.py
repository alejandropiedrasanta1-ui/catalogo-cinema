"""Ampliación con IA (súper-resolución) para que las páginas no se pixeleen al hacer zoom.

Usa Real-ESRGAN (realesrgan-ncnn-vulkan, modelo realesrgan-x4plus) incluido en recursos/realesrgan: corre en la
tarjeta de video (Vulkan), sin internet. Amplía 4× y luego se reduce con Lanczos al tamaño pedido (queda
súper-muestreado: bordes de textos y logos limpios). Si no hay GPU compatible o falla, se amplía con Lanczos y un
enfoque suave (nunca se deja de exportar)."""
import os
import subprocess
from pathlib import Path

import rutas

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CARPETA = "recursos/realesrgan"
MODELO = "realesrgan-x4plus"


def ejecutable():
    """Windows: realesrgan-ncnn-vulkan.exe · Mac: realesrgan-ncnn-vulkan (versión oficial para macOS, usa Metal vía
    MoltenVK). Los modelos (models/) son los mismos."""
    nombre = "realesrgan-ncnn-vulkan.exe" if rutas.ES_WINDOWS else "realesrgan-ncnn-vulkan"
    exe = Path(rutas.recurso(f"{CARPETA}/{nombre}"))
    if not exe.exists():
        return None
    if not rutas.ES_WINDOWS and not os.access(exe, os.X_OK):
        try:
            exe.chmod(0o755)
        except OSError:
            return None
    return exe


def disponible():
    return ejecutable() is not None


def _lanczos(im, ancho, alto):
    from PIL import ImageFilter
    from PIL import Image
    im = im.resize((ancho, alto), Image.LANCZOS)
    return im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def ampliar(origen, ancho, alto, destino):
    """Amplía la imagen origen (PNG) a ancho×alto y la guarda en destino (PNG). Devuelve "ia" o "lanczos"."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    origen, destino = Path(origen), Path(destino)
    exe = ejecutable()
    metodo = "lanczos"
    im = None
    if exe:
        tmp = destino.with_name(destino.stem + "_x4.png")
        try:
            r = subprocess.run([str(exe), "-i", str(origen), "-o", str(tmp), "-n", MODELO,
                                "-m", str(exe.parent / "models"), "-f", "png"],
                               capture_output=True, timeout=900, creationflags=SIN_VENTANA, cwd=str(exe.parent))
            if r.returncode == 0 and tmp.exists():
                with Image.open(tmp) as x4:
                    im = x4.convert("RGB").resize((ancho, alto), Image.LANCZOS)
                metodo = "ia"
        except (OSError, subprocess.SubprocessError):
            im = None
        finally:
            tmp.unlink(missing_ok=True)
    if im is None:
        with Image.open(origen) as o:
            im = _lanczos(o.convert("RGB"), ancho, alto)
    destino.parent.mkdir(parents=True, exist_ok=True)
    im.save(destino, "PNG", compress_level=3)
    return metodo
