"""Ubicaciones del programa: recursos incluidos (solo lectura), datos del usuario y salida."""
import os
import sys
from pathlib import Path

APP = "Catalogo Cinema Productions"
VERSION = "1.2.2"
ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"
CONGELADO = getattr(sys, "frozen", False)

RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CARPETA_APP = Path(sys.executable).resolve().parent if CONGELADO else Path(__file__).resolve().parent

if ES_WINDOWS:
    DATOS = Path(os.environ.get("APPDATA", Path.home())) / APP
elif ES_MAC:
    DATOS = Path.home() / "Library" / "Application Support" / APP
else:
    DATOS = Path.home() / ".config" / APP

CONFIG = DATOS / "config.json"
EDICIONES = DATOS / "ediciones.json"     # cambios hechos a los PSD (textos, fotos, capas visibles)
INDICE = DATOS / "indice.json"           # páginas de cada PSD y sus miniaturas
MINIATURAS = DATOS / "miniaturas"
IMAGENES = DATOS / "imagenes"            # fotos elegidas para reemplazar (PhotoCraft las lee de aquí)
TRABAJO = DATOS / "trabajo"              # PhotoCraft solo puede escribir aquí; luego se mueve al destino
HD = DATOS / "hd"                       # páginas ya ampliadas con IA (caché)

SALIDA_POR_DEFECTO = Path.home() / "Documents" / APP / "ENVIOS"
# el catálogo (secciones con los PSD) está en PROGRAMA\CATALOGO; instalado: Windows usa la del disco E:,
# Mac una carpeta en Documentos (se puede elegir otra en Ajustes › Carpeta del catálogo)
if not CONGELADO:
    CATALOGO_POR_DEFECTO = CARPETA_APP / "CATALOGO"
elif ES_MAC:
    CATALOGO_POR_DEFECTO = Path.home() / "Documents" / APP / "CATALOGO"
else:
    CATALOGO_POR_DEFECTO = Path(r"E:\CINEMA PRODUCTIONS\CATAGOLO COMPLETO\PROGRAMA\CATALOGO")


def abrir(ruta):
    """Abre una carpeta o archivo con el programa del sistema (Explorador / Finder)."""
    import subprocess
    ruta = str(ruta)
    if ES_WINDOWS:
        os.startfile(ruta)
    elif ES_MAC:
        subprocess.Popen(["open", ruta])
    else:
        subprocess.Popen(["xdg-open", ruta])


def recurso(relativa):
    p = Path(relativa)
    return p if p.is_absolute() else RECURSOS / p


CATALOGO_HD_INCLUIDO = RECURSOS / "CATALOGO HD"          # JPG + PDF de cada sección que trae el instalador
CATALOGO_HD_DOCUMENTOS = Path.home() / "Documents" / APP / "CATALOGO HD"


def copiar_catalogo_hd():
    """La primera vez (y en cada versión nueva) copia el catálogo HD incluido a Documentos para tenerlo a mano."""
    import shutil
    if not (CONGELADO and CATALOGO_HD_INCLUIDO.is_dir()):
        return
    marca = CATALOGO_HD_DOCUMENTOS / ".version"
    try:
        if marca.exists() and marca.read_text(encoding="utf-8").strip() == VERSION:
            return
        shutil.copytree(CATALOGO_HD_INCLUIDO, CATALOGO_HD_DOCUMENTOS, dirs_exist_ok=True)
        marca.write_text(VERSION, encoding="utf-8")
    except OSError:
        pass                                              # sin permiso o sin espacio: el programa sigue igual


def preparar_carpetas():
    for c in (DATOS, MINIATURAS, IMAGENES, TRABAJO, HD):
        c.mkdir(parents=True, exist_ok=True)
    if CONGELADO and ES_MAC:
        CATALOGO_POR_DEFECTO.mkdir(parents=True, exist_ok=True)
    copiar_catalogo_hd()
