"""Exporta las páginas elegidas para el cliente en alta calidad: imágenes (JPG o PNG) y/o un solo PDF.

Calidad (para que no se pixelee al hacer zoom):
- PhotoCraft dibuja cada página a su tamaño original y la guarda en PNG (sin pérdida).
- En «Alta» y «Máxima» la página se amplía con IA (Real-ESRGAN, ver ampliar.py): textos, logos y fotos nítidos.
  (No se usa el «Tamaño de imagen» de PhotoCraft: en varios PSD deformaba el diseño.)
- Lo ampliado queda en caché (rutas.HD): volver a enviar las mismas páginas es instantáneo.
- El JPG se hace con calidad alta y color completo (4:4:4), sin manchas alrededor de los textos de color.
- El PDF lleva esos mismos JPG tal cual (sin volver a comprimir) y cada página con su tamaño real."""
import hashlib
import re
import shutil
from datetime import date
from pathlib import Path

import ampliar
import config
import rutas

# lado mayor mínimo de cada página al exportar (0 = tamaño original del PSD)
NIVELES = {"normal": 0, "alta": 4400, "maxima": 6600}
FACTOR_MAX = 4.0
SEG_POR_MPX = 3.0   # para estimar cuánto tarda la IA (≈24 s una página de 2550×3300 en una RTX)


def limpio(texto):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto).strip().rstrip(".") or "Cliente"


def carpeta_envio(base, cliente):
    hoy = date.today()
    nombre = limpio(f"{cliente.strip() or 'Cliente'} - {hoy.day:02d}-{hoy.month:02d}-{hoy.year}")
    destino = Path(base) / nombre
    n = 2
    while destino.exists():
        destino = Path(base) / f"{nombre} ({n})"
        n += 1
    return destino


def factor(rect, nivel):
    objetivo = NIVELES.get(nivel, NIVELES["alta"])
    lado = max(rect[2], rect[3]) if rect else 0
    if not objetivo or not lado or lado >= objetivo:
        return 1.0
    return min(FACTOR_MAX, objetivo / lado)


def tamano_final(rect, nivel):
    f = factor(rect, nivel)
    return round(rect[2] * f), round(rect[3] * f)


def archivo_hd(indice, ediciones, rel, pid, nivel):
    """Dónde queda en caché la página ampliada (cambia si cambia el PSD, sus ediciones o la calidad)."""
    pag = indice.pagina(rel, pid)
    if not pag:
        return None
    w, h = tamano_final(pag["rect"], nivel)
    clave = f"{rel}|{indice.de(rel).get('clave')}|{ediciones.firma(rel)}|{pid}|{w}x{h}"
    return rutas.HD / f"{hashlib.sha1(clave.encode()).hexdigest()[:20]}.jpg"


def en_cache(indice, ediciones, rel, pid, nivel):
    pag = indice.pagina(rel, pid)
    if not pag or factor(pag["rect"], nivel) <= 1.001:
        return True   # no necesita IA: es rápido
    a = archivo_hd(indice, ediciones, rel, pid, nivel)
    return bool(a and a.exists())


def segundos_estimados(indice, ediciones, items, nivel):
    total = 0.0
    for rel, pid in items:
        pag = indice.pagina(rel, pid)
        if pag and not en_cache(indice, ediciones, rel, pid, nivel):
            total += 2 + SEG_POR_MPX * pag["rect"][2] * pag["rect"][3] / 1e6
        else:
            total += 1
    return total


def _escribir(origen, destino, calidad, ppi):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(origen) as im:
        if destino.suffix.lower() == ".png":
            im.save(destino, "PNG", dpi=(ppi, ppi), compress_level=6)
        else:
            im.convert("RGB").save(destino, "JPEG", quality=int(calidad), subsampling=0, optimize=True,
                                   dpi=(ppi, ppi))
    return destino


def pagina_hd(sesion, abrir, rect, visibles, nivel, cache=None):
    """La página como imagen de la calidad pedida (ruta). abrir() deja el PSD abierto (solo si hace falta).
    Devuelve (ruta, temporal?)."""
    if cache and cache.exists():
        return cache, False
    abrir()
    sesion.pagina(rect, visibles)
    if rect is None:
        info = sesion.doc["info"]
        rect = [0, 0, info["width"], info["height"]]
    png = sesion.guardar(rutas.TRABAJO / "pagina_original.png")
    f = factor(rect, nivel)
    if f <= 1.001:
        return png, True
    grande = rutas.TRABAJO / "pagina_hd.png"
    ampliar.ampliar(png, round(rect[2] * f), round(rect[3] * f), grande)
    png.unlink(missing_ok=True)
    if cache:   # se guarda en caché como JPG casi sin pérdida (97, color completo)
        _escribir(grande, cache, 97, 300)
    return grande, True


def guardar_pagina(sesion, rect, destino, nivel="alta", calidad=95, ppi=144, visibles=None, cache=None,
                   abrir=lambda: None):
    """Guarda la página (destino .jpg o .png) en la calidad elegida. Devuelve (ruta, ppi final)."""
    origen, temporal = pagina_hd(sesion, abrir, rect, visibles, nivel, cache)
    f = factor(rect, nivel) if rect else 1.0
    ppi_final = round(float(ppi) * f, 2)
    try:
        if Path(destino).suffix.lower() == ".jpg" and not temporal and int(calidad) >= 95:
            shutil.copyfile(origen, destino)   # ya está en JPG de alta calidad: tal cual
            _poner_dpi(destino, ppi_final)
        else:
            _escribir(origen, destino, calidad, ppi_final)
    finally:
        if temporal:
            Path(origen).unlink(missing_ok=True)
    return Path(destino), ppi_final


def _poner_dpi(jpg, ppi):
    """Cambia la resolución anotada del JPG (bytes 13-17 del encabezado JFIF) sin volver a comprimir."""
    with open(jpg, "r+b") as f:
        cab = f.read(20)
        if cab[6:11] == b"JFIF\x00":
            v = max(1, min(65535, round(ppi)))
            f.seek(13)
            f.write(bytes([1, v >> 8, v & 255, v >> 8, v & 255]))


def exportar(sesion, indice, ediciones, docs, items, destino, cliente, pdf=True, imagenes=True,
             formato="JPG", calidad=95, avisar=None, nivel="alta"):
    """items: [(rel, id de página)]. Devuelve {"carpeta", "imagenes": [...], "pdf": ruta o None}."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    ext = ".png" if formato.upper() == "PNG" else ".jpg"
    temporal = rutas.TRABAJO / "envio_pdf"
    shutil.rmtree(temporal, ignore_errors=True)
    rutas.HD.mkdir(parents=True, exist_ok=True)
    hechos = 0
    salida_img = [None] * len(items)
    salida_pdf = [None] * len(items)   # (jpg, ppi)

    for rel in dict.fromkeys(rel for rel, _ in items):   # cada PSD se abre una sola vez (y solo si hace falta)
        doc = docs[rel]
        ed = ediciones.de(rel)
        pasos, firma = config.pasos(ed), config.firma(ed)
        paginas = indice.paginas(rel)
        ppi = indice.de(rel).get("ppi") or 144

        def abrir(doc=doc, pasos=pasos, firma=firma):
            sesion.abrir(doc.ruta)
            sesion.preparar(pasos, firma)

        for i, (r, pid) in enumerate(items):
            if r != rel:
                continue
            pag = indice.pagina(rel, pid) or {"nombre": "", "rect": None}
            cache = archivo_hd(indice, ediciones, rel, pid, nivel) if pag["rect"] and \
                factor(pag["rect"], nivel) > 1.001 else None
            if avisar:
                w, h = tamano_final(pag["rect"], nivel) if pag["rect"] else (0, 0)
                que = "listo en caché" if cache and cache.exists() else (
                    "ampliando con IA…" if cache else "original")
                avisar(hechos, len(items), f"{doc.nombre} · {pag['nombre']}  ({w}×{h} px, {que})")
            nombre = limpio(f"{i + 1:02d} - {doc.nombre}" + (f" - {pag['nombre']}" if len(paginas) > 1 else ""))

            def una(dest, cal, rect=pag["rect"], vis=pag.get("visibles"), cache=cache, abrir=abrir):
                return sesion.con_reintento(doc.ruta, pasos, firma, lambda: guardar_pagina(
                    sesion, rect, dest, nivel, cal, ppi, vis, cache, abrir))
            if imagenes:
                ruta, p = una(destino / f"{nombre}{ext}", calidad)
                salida_img[i] = ruta
                if pdf and ext == ".jpg":
                    salida_pdf[i] = (ruta, p)
            if pdf and salida_pdf[i] is None:
                salida_pdf[i] = una(temporal / f"{i:03d}.jpg", max(int(calidad), 95))
            hechos += 1

    archivo_pdf = None
    if pdf:
        if avisar:
            avisar(hechos, len(items), "Armando el PDF…")
        archivo_pdf = destino / f"{limpio(cliente.strip() or 'Catalogo')} - Cinema Productions.pdf"
        armar_pdf(salida_pdf, archivo_pdf)
        shutil.rmtree(temporal, ignore_errors=True)
    if avisar:
        avisar(len(items), len(items), "Listo")
    return {"carpeta": destino, "imagenes": [p for p in salida_img if p], "pdf": archivo_pdf}


MARCA_HD = ".catalogo_hd"   # señala que la carpeta la creó el programa (se puede vaciar y rehacer)


def catalogo_hd(sesion, indice, ediciones, docs, secciones, destino, nivel="alta", calidad=95, avisar=None):
    """«Pulir todo el catálogo»: amplía con IA todas las páginas y deja en destino una carpeta por sección
    con cada página en JPG de alta calidad y un PDF de la sección. Los PSD originales no se tocan.
    secciones: {sección: [Doc]}."""
    destino = Path(destino)
    if destino.exists() and any(destino.iterdir()) and not (destino / MARCA_HD).exists():
        raise RuntimeError(f"La carpeta {destino} ya tiene otros archivos: elige una carpeta vacía.")
    todas = [(d.rel, p["id"]) for ds in secciones.values() for d in ds for p in indice.paginas(d.rel)]
    preparar_hd(sesion, indice, ediciones, docs, todas, nivel,
                (lambda h, t, txt: avisar(h, t + len(secciones), f"IA: {txt}")) if avisar else None)
    for seccion in secciones:
        shutil.rmtree(destino / limpio(seccion.title()), ignore_errors=True)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / MARCA_HD).write_text("Carpeta creada por Catálogo Cinema Productions (Pulir todo el catálogo).",
                                    encoding="utf-8")
    hechos = len(todas)
    for seccion, ds in secciones.items():
        items = [(d.rel, p["id"]) for d in ds for p in indice.paginas(d.rel)]
        if not items:
            continue
        if avisar:
            avisar(hechos, len(todas) + len(secciones), f"Sección {seccion.title()}")
        exportar(sesion, indice, ediciones, docs, items, destino / limpio(seccion.title()), seccion.title(),
                 pdf=True, imagenes=True, formato="JPG", calidad=calidad, nivel=nivel)
        hechos += 1
    if avisar:
        avisar(1, 1, "Listo")
    return destino


def preparar_hd(sesion, indice, ediciones, docs, items, nivel="alta", avisar=None):
    """Deja en caché las páginas ampliadas con IA (para que luego enviar sea instantáneo)."""
    rutas.HD.mkdir(parents=True, exist_ok=True)
    pendientes = [(r, p) for r, p in items if not en_cache(indice, ediciones, r, p, nivel)]
    for n, rel in enumerate(dict.fromkeys(r for r, _ in pendientes)):
        doc = docs[rel]
        ed = ediciones.de(rel)
        pasos, firma = config.pasos(ed), config.firma(ed)

        def abrir(doc=doc, pasos=pasos, firma=firma):
            sesion.abrir(doc.ruta)
            sesion.preparar(pasos, firma)
        for r, pid in pendientes:
            if r != rel:
                continue
            pag = indice.pagina(rel, pid)
            if avisar:
                avisar(pendientes.index((r, pid)), len(pendientes), f"{doc.nombre} · {pag['nombre']}")
            cache = archivo_hd(indice, ediciones, rel, pid, nivel)
            ruta, temporal = sesion.con_reintento(doc.ruta, pasos, firma, lambda: pagina_hd(
                sesion, abrir, pag["rect"], pag.get("visibles"), nivel, cache))
            if temporal:
                Path(ruta).unlink(missing_ok=True)
    if avisar:
        avisar(len(pendientes), len(pendientes), "Listo")
    return len(pendientes)


def armar_pdf(paginas, archivo):
    """PDF con una página por JPG [(ruta, ppi)], insertando el JPG tal cual (sin recomprimir).
    Cada página mide lo que mide el diseño (píxeles ÷ ppi)."""
    from PIL import Image
    objetos = {}
    n = len(paginas)
    kids = " ".join(f"{3 + 3 * i} 0 R" for i in range(n))
    objetos[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    for i, (ruta, ppi) in enumerate(paginas):
        with Image.open(ruta) as im:
            w, h = im.size
            gris = im.mode == "L"
        datos = Path(ruta).read_bytes()
        ancho, alto = w / float(ppi or 72) * 72, h / float(ppi or 72) * 72
        pg, ct, img = 3 + 3 * i, 4 + 3 * i, 5 + 3 * i
        objetos[pg] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho:.2f} {alto:.2f}] "
                       f"/Resources << /XObject << /Im0 {img} 0 R >> >> /Contents {ct} 0 R >>").encode()
        contenido = f"q {ancho:.2f} 0 0 {alto:.2f} 0 0 cm /Im0 Do Q".encode()
        objetos[ct] = b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream"
        objetos[img] = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
                        f"/ColorSpace /{'DeviceGray' if gris else 'DeviceRGB'} /BitsPerComponent 8 "
                        f"/Filter /DCTDecode /Length {len(datos)} >>\nstream\n").encode() + datos + b"\nendstream"
    archivo = Path(archivo)
    tmp = archivo.with_suffix(".pdf.tmp")
    with open(tmp, "wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        posiciones = {}
        for num in sorted(objetos):
            posiciones[num] = f.tell()
            f.write(f"{num} 0 obj\n".encode() + objetos[num] + b"\nendobj\n")
        xref = f.tell()
        total = max(objetos) + 1
        f.write(f"xref\n0 {total}\n0000000000 65535 f \n".encode())
        for num in range(1, total):
            f.write(f"{posiciones[num]:010d} 00000 n \n".encode())
        f.write(f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    tmp.replace(archivo)
    return archivo
