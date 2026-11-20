"""El catálogo: secciones (carpetas de primer nivel), documentos PSD y sus páginas (mesas de trabajo),
con miniaturas en caché que se rehacen solo si el PSD o sus ediciones cambian."""
import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

import ampliar
import config
import rutas

EXTENSIONES = {".psd", ".psb"}
IGNORAR = {"PROGRAMA", "INSTALADOR", "CATALOGO HD"}
LADO_MINI = 2048   # lado mayor de las miniaturas (también sirven para ver la página en grande)
VERSION_MINI = 4  # súbelo para que todas las miniaturas se vuelvan a hacer


@dataclass
class Doc:
    rel: str          # ruta relativa a la carpeta del catálogo (clave de todo)
    ruta: Path
    nombre: str
    seccion: str
    sub: str          # subcarpetas dentro de la sección («VERSION 2 › PSD»)


def escanear(raiz):
    """{sección: [Doc]} en orden alfabético."""
    raiz = Path(raiz)
    secciones = {}
    if not raiz.is_dir():
        return secciones
    for carpeta in sorted(raiz.iterdir(), key=lambda p: p.name.lower()):
        if not carpeta.is_dir() or carpeta.name in IGNORAR or carpeta.name.startswith("."):
            continue
        docs = []
        for f in carpeta.rglob("*"):
            if f.suffix.lower() in EXTENSIONES and f.is_file() and not f.name.startswith("._"):
                rel = f.relative_to(raiz).as_posix()
                sub = " › ".join(f.parent.relative_to(carpeta).parts)
                docs.append(Doc(rel, f, f.stem, carpeta.name, sub))
        if docs:
            docs.sort(key=lambda d: (d.sub.lower(), _orden_natural(d.nombre)))
            secciones[carpeta.name] = docs
    return secciones


def _orden_natural(texto):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", texto)]


PATRON_GRUPO = re.compile(r"^\s*(p[aá]g(ina)?|page|hoja|plana)\.?\s*#?\s*(\d+)\s*$", re.I)


def paginas_de(info):
    """Las páginas del PSD:
    - mesas de trabajo visibles (de arriba abajo, de izquierda a derecha);
    - o grupos «pagina 1», «pagina 2»… (una página por grupo: se muestra solo ese grupo);
    - o el documento entero."""
    capas = info.get("layers") or []
    completo = [0, 0, info["width"], info["height"]]
    mesas = [l for l in capas if l.get("artboard") and l.get("visible", True)]
    if mesas:
        mesas.sort(key=lambda l: (l["artboard"]["rect"][1], l["artboard"]["rect"][0]))
        return [dict(id=l["id"], nombre=l.get("name") or f"Página {i + 1}", rect=list(l["artboard"]["rect"]))
                for i, l in enumerate(mesas)]
    grupos = [l for l in capas if l.get("kind") == "Group" and PATRON_GRUPO.match(l.get("name") or "")]
    if len(grupos) >= 2:
        grupos.sort(key=lambda l: int(PATRON_GRUPO.match(l["name"]).group(3)))
        ids = [g["id"] for g in grupos]
        return [dict(id=g["id"], nombre=g["name"].strip().capitalize(), rect=completo,
                     visibles={str(i): i == g["id"] for i in ids}) for g in grupos]
    return [dict(id=0, nombre="Página 1", rect=completo)]


def capas_de_pagina(info, pid):
    """Las capas de una página como lista plana [(capa, profundidad)], en el orden del panel de capas."""
    planas = []

    def recorrer(ls, nivel):
        for l in ls:
            planas.append((l, nivel))
            recorrer(l.get("children") or [], nivel + 1)
    raiz = info.get("layers") or []
    if pid:
        raiz = next(([l] for l in raiz if l["id"] == pid), [])
        recorrer(raiz[0].get("children") or [] if raiz else [], 0)
    else:
        recorrer(raiz, 0)
    return planas


def _clave_archivo(ruta):
    st = Path(ruta).stat()
    return f"{int(st.st_mtime)}-{st.st_size}"


def _carpeta_mini(rel):
    return rutas.MINIATURAS / hashlib.sha1(rel.encode()).hexdigest()[:16]


class Indice:
    """indice.json: {rel: {clave, firma, ancho, alto, ppi, paginas: [{id, nombre, rect}], miniaturas: {id: archivo},
    error}}"""

    def __init__(self):
        try:
            self.datos = json.loads(rutas.INDICE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.datos = {}

    def guardar(self):
        rutas.INDICE.parent.mkdir(parents=True, exist_ok=True)
        tmp = rutas.INDICE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.datos, ensure_ascii=False), encoding="utf-8")
        tmp.replace(rutas.INDICE)

    def de(self, rel):
        return self.datos.get(rel) or {}

    def paginas(self, rel):
        return self.de(rel).get("paginas") or []

    def pagina(self, rel, pid):
        return next((p for p in self.paginas(rel) if p["id"] == pid), None)

    def miniatura(self, rel, pid):
        archivo = (self.de(rel).get("miniaturas") or {}).get(str(pid))
        if archivo:
            ruta = _carpeta_mini(rel) / archivo
            if ruta.exists():
                return ruta
        return None

    def vigente(self, doc, firma):
        e = self.de(doc.rel)
        try:
            clave = _clave_archivo(doc.ruta)
        except OSError:
            return True   # el archivo ya no está: no hay nada que rehacer
        if e.get("clave") != clave or e.get("vmini") != VERSION_MINI:
            return False
        if e.get("error"):
            return True   # ya falló con este mismo archivo: no se reintenta solo
        return e.get("firma") == firma and all(self.miniatura(doc.rel, p["id"]) for p in e.get("paginas") or [])

    def procesar(self, sesion, doc, ed, avisar=None):
        """Abre el PSD, aplica las ediciones y dibuja la miniatura de cada página."""
        from PIL import Image
        clave = _clave_archivo(doc.ruta)
        firma = config.firma(ed)
        try:
            info = sesion.abrir(doc.ruta)
            paginas = paginas_de(info)
            pasos = config.pasos(ed)
            sesion.preparar(pasos, firma)
            carpeta = _carpeta_mini(doc.rel)
            carpeta.mkdir(parents=True, exist_ok=True)
            minis = {}
            for i, pag in enumerate(paginas):
                if avisar:
                    avisar(i, len(paginas))
                nombre = f"{pag['id']}-{firma}-v{VERSION_MINI}.jpg"

                def miniatura(pag=pag, nombre=nombre):
                    sesion.pagina(pag["rect"], pag.get("visibles"))
                    w, h = pag["rect"][2], pag["rect"][3]
                    tmp = sesion.guardar(rutas.TRABAJO / "miniatura.png")
                    if max(w, h) < LADO_MINI:   # página chica: se amplía con IA para verla nítida
                        f = LADO_MINI / max(w, h)
                        ampliar.ampliar(tmp, round(w * f), round(h * f), tmp)
                    with Image.open(tmp) as im:
                        im = im.convert("RGB")
                        im.thumbnail((LADO_MINI, LADO_MINI), Image.LANCZOS)
                        im.save(carpeta / nombre, "JPEG", quality=92, subsampling=0, optimize=True)
                    tmp.unlink(missing_ok=True)
                sesion.con_reintento(doc.ruta, pasos, firma, miniatura)
                minis[str(pag["id"])] = nombre
            for viejo in carpeta.glob("*.jpg"):
                if viejo.name not in minis.values():
                    viejo.unlink(missing_ok=True)
            self.datos[doc.rel] = dict(clave=clave, firma=firma, ancho=info["width"], alto=info["height"],
                                       ppi=info.get("resolution") or 72, paginas=paginas, miniaturas=minis,
                                       vmini=VERSION_MINI)
        except Exception as e:
            if getattr(sesion, "apagada", False):
                raise   # se cerró el programa a medias: no es un error del PSD (se reintenta al abrir)
            previo = self.datos.get(doc.rel) or {}
            self.datos[doc.rel] = {**previo, "clave": clave, "error": str(e)}
            sesion.cerrar()
            raise
        finally:
            self.guardar()

    def olvidar(self, rel=None):
        """Borra las miniaturas (de un PSD o de todos) para que se vuelvan a hacer."""
        import shutil
        rels = [rel] if rel else list(self.datos)
        for r in rels:
            shutil.rmtree(_carpeta_mini(r), ignore_errors=True)
            self.datos.pop(r, None)
        self.guardar()
