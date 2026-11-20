"""Ajustes del usuario (config.json) y ediciones guardadas de cada PSD (ediciones.json)."""
import hashlib
import json

import rutas

POR_DEFECTO = dict(
    carpeta_catalogo=str(rutas.CATALOGO_POR_DEFECTO),
    carpeta_salida=str(rutas.SALIDA_POR_DEFECTO),
    photocraft_cli="",
    calidad_jpg=95,
    calidad_envio="alta",    # normal | alta | maxima (ver envio.NIVELES)
    tema="Oscuro",
    excluir=[],              # PSD (ruta relativa) que no se muestran en el catálogo
    enviar_pdf=True,
    enviar_imagenes=True,
    formato_imagen="JPG",
)


def _leer(ruta, defecto):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)


def cargar():
    cfg = dict(POR_DEFECTO)
    cfg.update(_leer(rutas.CONFIG, {}))
    if not cfg.get("hd"):   # versión 1.1: más calidad por defecto
        cfg["calidad_jpg"] = max(int(cfg.get("calidad_jpg", 95)), 95)
        cfg["hd"] = True
    return cfg


def guardar(cfg):
    _escribir(rutas.CONFIG, cfg)


class Ediciones:
    """Por PSD: {"textos": {id: texto}, "visibles": {id: bool}, "imagenes": {id: ruta}, "nombres": {id: nombre}}.
    No se toca el PSD original: los cambios se aplican al dibujar las miniaturas y al exportar."""

    def __init__(self):
        self.datos = _leer(rutas.EDICIONES, {})

    def de(self, rel):
        ed = self.datos.get(rel) or {}
        return {k: dict(ed.get(k) or {}) for k in ("textos", "visibles", "imagenes", "nombres", "originales")}

    def poner(self, rel, ed):
        if vacia(ed):
            self.datos.pop(rel, None)
        else:
            self.datos[rel] = ed
        _escribir(rutas.EDICIONES, self.datos)

    def firma(self, rel):
        return firma(self.de(rel))


def vacia(ed):
    return not any(ed.get(k) for k in ("textos", "visibles", "imagenes"))


def firma(ed):
    if vacia(ed):
        return "original"
    datos = {k: ed.get(k) for k in ("textos", "visibles", "imagenes")}
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def reemplazos(antes, despues):
    """Cambios mínimos de antes → despues como [{start, end, text}], del final al principio (así los índices
    de los anteriores siguen valiendo)."""
    import difflib
    ops = difflib.SequenceMatcher(None, antes, despues, autojunk=False).get_opcodes()
    return [{"start": i1, "end": i2, "text": despues[j1:j2]} for tag, i1, i2, j1, j2 in reversed(ops)
            if tag != "equal"]


def pasos(ed):
    """Los cambios como pasos de PhotoCraft: primero fotos, luego textos y capas visibles."""
    p = []
    for lid, ruta in (ed.get("imagenes") or {}).items():
        p.append(("doc.replaceSmartObject", {"layer": int(lid), "path": ruta}))
    originales = ed.get("originales") or {}
    for lid, texto in (ed.get("textos") or {}).items():
        if lid in originales:   # solo las letras que cambian: conserva colores y estilos de cada tramo
            p += [("engine.execute", {"command": "type.edit", "params": {"layer": int(lid), "replace": r}})
                  for r in reemplazos(originales[lid], texto)]
        else:
            p.append(("engine.execute", {"command": "type.edit", "params": {"layer": int(lid), "text": texto}}))
    for lid, si in (ed.get("visibles") or {}).items():
        p.append(("engine.execute", {"command": "layer.setProps", "params": {"layer": int(lid), "visible": bool(si)}}))
    return p
