# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para Windows (carpeta con .exe) y Mac (.app).
# Se usa desde "CREAR INSTALADOR WINDOWS.bat" o "CREAR APP MAC.command" (y GitHub Actions para Mac).
import re
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).parent
ES_MAC = sys.platform == "darwin"
NOMBRE = "Catalogo Cinema"
VERSION = re.search(r'VERSION\s*=\s*"([^"]+)"', (RAIZ / "rutas.py").read_text(encoding="utf-8")).group(1)

datas = [
    (str(RAIZ / "recursos" / "icono.png"), "recursos"),
    (str(RAIZ / "recursos" / "icono.ico"), "recursos"),
    (str(RAIZ / "recursos" / "ilustracion_vacio.png"), "recursos"),
    (str(RAIZ / "recursos" / "ilustracion_vacio_claro.png"), "recursos"),
    (str(RAIZ / "recursos" / "iconos"), "recursos/iconos"),
    # ampliador IA (Real-ESRGAN ncnn Vulkan, BSD-3): modelo x4plus + el ejecutable de cada sistema
    (str(RAIZ / "recursos" / "realesrgan" / "models"), "recursos/realesrgan/models"),
    (str(RAIZ / "recursos" / "realesrgan" / "LICENCIA.txt"), "recursos/realesrgan"),
]
if ES_MAC:
    mac = RAIZ / "recursos" / "realesrgan" / "realesrgan-ncnn-vulkan"   # lo descarga CREAR APP MAC / GitHub Actions
    if mac.exists():
        datas.append((str(mac), "recursos/realesrgan"))
else:
    datas += [(str(RAIZ / "recursos" / "realesrgan" / n), "recursos/realesrgan")
              for n in ("realesrgan-ncnn-vulkan.exe", "vcomp140.dll")]
# catálogo HD (JPG + PDF de cada sección): el programa lo copia a Documentos al abrir (rutas.copiar_catalogo_hd)
HD = RAIZ / "CATALOGO" / "CATALOGO HD"
if HD.is_dir():
    datas.append((str(HD), "CATALOGO HD"))

a = Analysis(
    [str(RAIZ / "catalogo_cinema.py")],
    pathex=[str(RAIZ)],
    datas=datas,
    # scipy/numpy/colorthief: solo para el efecto acrílico opcional de Fluent-Widgets (no se usa)
    excludes=["tkinter", "scipy", "numpy", "colorthief"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icono = str(RAIZ / "recursos" / ("icono.png" if ES_MAC else "icono.ico"))
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NOMBRE,
    console=False,
    icon=icono,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NOMBRE)

if ES_MAC:
    app = BUNDLE(
        coll,
        name=f"{NOMBRE}.app",
        icon=icono,
        bundle_identifier="com.cinemaproductions.catalogo",
        info_plist={
            "CFBundleDisplayName": "Catálogo Cinema Productions",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.business",
        },
    )
