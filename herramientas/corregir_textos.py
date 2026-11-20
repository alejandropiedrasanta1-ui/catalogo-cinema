"""Correcciones de ortografía seguras para TODOS los PSD del catálogo (revisión del 20-11-2026).

No toca los PSD: guarda los cambios como ediciones del programa (ediciones.json) que se aplican al dibujar y al
exportar (se deshacen en el Editor con «Volver al original»). Solo corrige lo que no cambia el sentido: tildes,
letras cirílicas pegadas, palabras unidas, espacios sueltos y «*» usado como «x» en medidas.

SEGURIDAD: PhotoCraft redibuja una capa de texto al editarla, y no siempre igual que Photoshop (viñetas,
interlineado, fuentes que faltan). Por eso, antes de corregir una capa se prueba un «cambio vacío» y se compara
con el original: si la capa no queda idéntica, NO se corrige y se anota para hacerlo en Photoshop.
Las correcciones cambian solo las letras necesarias (los colores y estilos de cada tramo se conservan).

  python herramientas/corregir_textos.py            muestra qué se corregiría (no guarda nada)
  python herramientas/corregir_textos.py --aplicar  guarda las correcciones seguras en ediciones.json
Escribe el informe en herramientas/informe_correcciones.txt
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import catalogo  # noqa: E402
import config  # noqa: E402
import photocraft  # noqa: E402
import rutas  # noqa: E402

TILDES = {
    "limite": "límite", "galeria": "galería", "album": "álbum", "albun": "álbum", "trailer": "tráiler",
    "segun": "según", "buzon": "buzón", "fria": "fría", "codigo": "código", "aereas": "aéreas",
    "dinamicas": "dinámicas", "animacion": "animación", "cafeteria": "cafetería", "maxima": "máxima",
    "paginas": "páginas", "publco": "público", "dia": "día", "rodage": "rodaje", "eleccion": "elección",
    "fotografias": "fotografías",
}
CIRILICAS = str.maketrans({"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
                           "С": "C", "Т": "T", "Х": "X", "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
                           "х": "x"})
TITULOS = {("salon de belleza.psd", "RESTAURANTE"): "SALÓN DE BELLEZA"}   # títulos copiados de otro PSD
UMBRAL = 4.0   # diferencia media máx. (0-255) dentro de la capa con un «cambio vacío»


def _caso(original, nueva):
    if original.isupper():
        return nueva.upper()
    if original[:1].isupper():
        return nueva[:1].upper() + nueva[1:]
    return nueva


def corregir(texto):
    t = texto.translate(CIRILICAS)
    t = re.sub(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+", lambda m: _caso(m.group(0), TILDES[m.group(0).lower()])
               if m.group(0).lower() in TILDES else m.group(0), t)
    t = t.replace("públco", "público")
    t = re.sub(r"\b(HORAS|horas|Horas) (MAS|mas|Mas)\b", lambda m: f"{m.group(1)} {_caso(m.group(2), 'más')}", t)
    t = t.replace("DELPAQUETE", "DEL PAQUETE").replace("FotoS", "Fotos")
    t = re.sub(r"(\d)\s*\*\s*(\d)", r"\1x\2", t)
    t = re.sub(r"\(([^()\n]*?\S) {2,}(\S[^()\n]*?)\)", r"(\1 \2)", t)          # espacio doble dentro de (…)
    t = re.sub(r"(^|\n) (?=[A-Za-zÁÉÍÓÚÑáéíóúñ¡\d])", r"\1", t)                 # UN espacio suelto al inicio
    t = t.replace("proyectos.incluyendo", "proyectos, incluyendo")
    t = re.sub(r"^¡agenda", "¡Agenda", t)
    return t


def _caja(capa, rect):
    b = capa.get("bounds")
    if isinstance(b, str):
        b = [float(v) for v in b.split()]
    if not b:
        return None
    x, y, w, h = b
    m = 12
    return (max(0, int(x - rect[0] - m)), max(0, int(y - rect[1] - m)),
            min(rect[2], int(x - rect[0] + w + m)), min(rect[3], int(y - rect[1] + h + m)))


def _diferencia(a, b, caja):
    from PIL import ImageChops, ImageStat
    if not caja or caja[2] <= caja[0] or caja[3] <= caja[1]:
        return 0.0
    d = ImageChops.difference(a.crop(caja), b.crop(caja)).convert("L")
    return ImageStat.Stat(d).mean[0]


def _render(ses, pag, pasos_extra=()):
    from PIL import Image
    d = ses.doc
    ses.lote([ses.cmd("history.selectSnapshot", {"snapshot": d["orig"]}), *pasos_extra])
    prueba = ses.lote([ses.cmd("history.newSnapshot", {"name": "prueba"})])[0]["snapshot"]
    d["editado"] = prueba   # pagina() vuelve a esta instantánea: con los cambios de prueba puestos
    try:
        ses.pagina(pag["rect"], pag.get("visibles"))
        ruta = ses.guardar(rutas.TRABAJO / "prueba_texto.png")
        im = Image.open(ruta).convert("RGB")
        im.load()
        ruta.unlink(missing_ok=True)
    finally:
        d["editado"], d["firma"] = d["orig"], None
        try:
            ses.lote([ses.cmd("history.deleteSnapshot", {"snapshot": prueba})])
        except photocraft.ErrorPhotoCraft:
            pass
    return im


def main(aplicar):
    cfg = config.cargar()
    secs = catalogo.escanear(cfg["carpeta_catalogo"])
    eds = config.Ediciones()
    ses = photocraft.Sesion()
    ses.configurar(cfg.get("photocraft_cli") or "", [cfg["carpeta_catalogo"]])
    ok, rechazadas = [], []
    for docs in secs.values():
        for d in docs:
            info = ses.abrir(d.ruta)
            ed = eds.de(d.rel)
            for pag in catalogo.paginas_de(info):
                base = None
                for capa, _ in catalogo.capas_de_pagina(info, pag["id"]):
                    if capa.get("kind") != "Type":
                        continue
                    lid = str(capa["id"])
                    original = (capa.get("text") or {}).get("text", "")
                    nuevo = TITULOS.get((Path(d.rel).name, original.strip()), corregir(original))
                    if nuevo == original:
                        continue
                    if base is None:
                        base = _render(ses, pag)
                    caja = _caja(capa, pag["rect"])
                    # 1) ¿PhotoCraft redibuja esta capa igual que el original? (cambio vacío)
                    otra = "#" if original[:1] != "#" else "%"   # cambiar y devolver: obliga a redibujar
                    vacio = [ses.cmd("type.edit", {"layer": int(lid),
                                                   "replace": {"start": 0, "end": 1, "text": otra}}),
                             ses.cmd("type.edit", {"layer": int(lid),
                                                   "replace": {"start": 0, "end": 1, "text": original[:1]}})]
                    dif = _diferencia(base, _render(ses, pag, vacio), caja)
                    linea = f"{d.rel} · {pag['nombre']} · capa {lid} ({(capa.get('text') or {}).get('font')})\n" \
                            f"   - {original!r}\n   + {nuevo!r}"
                    if dif > UMBRAL:
                        rechazadas.append(f"{linea}\n   ✗ PhotoCraft no la redibuja igual (dif {dif:.1f}): "
                                          "corregir en Photoshop")
                        continue
                    ok.append(f"{linea}\n   ✓ segura (dif {dif:.2f})")
                    ed["textos"][lid] = nuevo
                    ed["originales"][lid] = original
                    ed["nombres"][lid] = capa.get("name") or ""
            if aplicar:
                eds.poner(d.rel, ed)
            ses.cerrar()
    informe = ["CORRECCIONES APLICADAS" if aplicar else "CORRECCIONES SEGURAS (no se guardó nada)", *ok, "",
               "NO SE PUEDEN CORREGIR AQUÍ (hacerlo en Photoshop)", *rechazadas]
    (Path(__file__).parent / "informe_correcciones.txt").write_text("\n".join(informe), encoding="utf-8")
    print(f"seguras: {len(ok)} · para Photoshop: {len(rechazadas)}")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
