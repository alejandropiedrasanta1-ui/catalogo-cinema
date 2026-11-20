"""Estado compartido por todas las pantallas: catálogo, índice, ediciones, selección para el envío y el
Trabajador (un hilo que hace todo lo de PhotoCraft, en orden, sin congelar la ventana)."""
import threading
import traceback

from PySide6.QtCore import QObject, QSize, QThread, Signal
from PySide6.QtGui import QImageReader, QPixmap

import catalogo
import config
import photocraft


class Trabajador(QThread):
    """Cola de trabajos. Los urgentes (vista del editor, exportar) pasan antes que las miniaturas.
    Un trabajo con «clave» reemplaza al pendiente con la misma clave (p. ej. la vista en vivo)."""
    en_principal = Signal(object)   # función sin argumentos que se corre en el hilo de la ventana
    ocupado = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cond = threading.Condition()
        self.urgentes, self.normales = [], []
        self.salir = False
        self.corriendo = False
        self.en_principal.connect(lambda f: f())

    def enviar(self, fn, listo=None, fallo=None, clave=None, urgente=False):
        with self.cond:
            cola = self.urgentes if urgente else self.normales
            if clave is not None:
                cola[:] = [t for t in cola if t[3] != clave]
            cola.append((fn, listo, fallo, clave))
            self.cond.notify()

    def cancelar(self, prefijo):
        with self.cond:
            for cola in (self.urgentes, self.normales):
                cola[:] = [t for t in cola if not (isinstance(t[3], tuple) and t[3][0] == prefijo)]

    def pendientes(self):
        """Trabajos en cola más el que está corriendo."""
        with self.cond:
            return len(self.urgentes) + len(self.normales) + (1 if self.corriendo else 0)

    def principal(self, f):
        self.en_principal.emit(f)

    def detener(self):
        with self.cond:
            self.salir = True
            self.cond.notify()
        self.wait(3000)

    def run(self):
        while True:
            with self.cond:
                while not (self.urgentes or self.normales or self.salir):
                    self.ocupado.emit(False)
                    self.cond.wait()
                if self.salir:
                    return
                fn, listo, fallo, _ = (self.urgentes or self.normales).pop(0)
                self.corriendo = True
            self.ocupado.emit(True)
            try:
                r = fn()
            except Exception as e:
                self.corriendo = False
                if self.salir:   # se está cerrando el programa: el error es por eso
                    return
                traceback.print_exc()
                if fallo:
                    self.principal(lambda e=e: fallo(e))
                continue
            self.corriendo = False
            if listo:
                self.principal(lambda r=r: listo(r))


class Estado(QObject):
    catalogo_cambiado = Signal()
    miniatura_lista = Signal(str)            # rel
    progreso = Signal(str, int, int)         # texto, hechos, total
    seleccion_cambiada = Signal()
    abrir_editor = Signal(str, int)          # rel, id de página
    ir_a_envio = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.ediciones = config.Ediciones()
        self.indice = catalogo.Indice()
        self.sesion = photocraft.Sesion()
        self.secciones = {}
        self.docs = {}
        self.seleccion = []                  # [(rel, id)]
        self._pix = {}
        self._mini_total = 0
        self._mini_hechos = 0
        self.trabajador = Trabajador()
        self.trabajador.start()
        self.configurar_sesion()

    def configurar_sesion(self):
        self.sesion_pendiente = (self.cfg.get("photocraft_cli") or "", [self.cfg["carpeta_catalogo"]])
        self.trabajador.enviar(lambda: self.sesion.configurar(*self.sesion_pendiente), urgente=True)

    def cerrar(self):
        """Al cerrar la ventana: se vacía la cola, se cierra PhotoCraft (así el trabajo en curso termina al
        instante) y se espera al hilo. Destruir el hilo mientras corre hace que Qt cierre el programa a la fuerza."""
        t = self.trabajador
        with t.cond:
            t.urgentes.clear()
            t.normales.clear()
            t.salir = True
            t.cond.notify()
        self.sesion.apagar()
        if not t.wait(15000):
            self.sesion.cerrar()
            t.wait(5000)

    # ---- catálogo ----
    def recargar(self):
        self.secciones = catalogo.escanear(self.cfg["carpeta_catalogo"])
        self.docs = {d.rel: d for ds in self.secciones.values() for d in ds}
        self.seleccion = [s for s in self.seleccion if s[0] in self.docs]
        self.catalogo_cambiado.emit()
        self.preparar_miniaturas()

    def visibles(self, seccion=None):
        excluir = set(self.cfg.get("excluir") or [])
        secs = [seccion] if seccion else list(self.secciones)
        return [d for s in secs for d in self.secciones.get(s, []) if d.rel not in excluir]

    def preparar_miniaturas(self, solo=None):
        self.trabajador.cancelar("mini")
        docs = [self.docs[solo]] if solo else self.visibles()
        pendientes = [d for d in docs if not self.indice.vigente(d, self.ediciones.firma(d.rel))]
        self._mini_total, self._mini_hechos = len(pendientes), 0
        if not pendientes:
            self.progreso.emit("", 0, 0)
            return
        for d in pendientes:
            self.trabajador.enviar(lambda d=d: self._miniaturas_de(d),
                                   listo=lambda _, d=d: self._mini_lista(d.rel),
                                   fallo=lambda e, d=d: self._mini_lista(d.rel, e), clave=("mini", d.rel))

    def _miniaturas_de(self, d):
        def avisar(i, n):
            self.trabajador.principal(lambda: self.progreso.emit(
                f"Preparando {d.nombre} ({i + 1}/{n} págs.)", self._mini_hechos, self._mini_total))
        self.indice.procesar(self.sesion, d, self.ediciones.de(d.rel), avisar)

    def _mini_lista(self, rel, error=None):
        self._mini_hechos += 1
        self._pix = {k: v for k, v in self._pix.items() if k[0] != rel}
        self.miniatura_lista.emit(rel)
        if self._mini_hechos >= self._mini_total:
            self.progreso.emit("", 0, 0)
        else:
            self.progreso.emit("Preparando miniaturas…", self._mini_hechos, self._mini_total)

    LADO_LIGERO = 720   # las tarjetas usan una copia liviana; «Ver en grande» carga la de 2048 px

    def pixmap(self, rel, pid, grande=False):
        clave = (rel, pid, grande)
        if clave not in self._pix:
            ruta = self.indice.miniatura(rel, pid)
            pm = None
            if ruta:
                lector = QImageReader(str(ruta))
                if not grande:
                    t = lector.size()
                    lado = max(t.width(), t.height())
                    if lado > self.LADO_LIGERO:
                        e = self.LADO_LIGERO / lado
                        lector.setScaledSize(QSize(round(t.width() * e), round(t.height() * e)))
                img = lector.read()
                pm = QPixmap.fromImage(img) if not img.isNull() else None
            if grande:   # pocas en memoria (≈20 MB cada una)
                for k in [k for k in self._pix if k[2]][:-3]:
                    del self._pix[k]
            self._pix[clave] = pm
        return self._pix[clave]

    # ---- selección para el envío ----
    def seleccionada(self, rel, pid):
        return (rel, pid) in self.seleccion

    def alternar(self, rel, pid):
        if (rel, pid) in self.seleccion:
            self.seleccion.remove((rel, pid))
        else:
            self.seleccion.append((rel, pid))
        self.seleccion_cambiada.emit()

    def agregar(self, items):
        for it in items:
            if it not in self.seleccion:
                self.seleccion.append(it)
        self.seleccion_cambiada.emit()

    def quitar(self, items):
        self.seleccion = [s for s in self.seleccion if s not in items]
        self.seleccion_cambiada.emit()

    def poner_seleccion(self, items):
        self.seleccion = list(items)
        self.seleccion_cambiada.emit()

    def nombre_pagina(self, rel, pid):
        d = self.docs.get(rel)
        pag = self.indice.pagina(rel, pid)
        if not d:
            return rel
        if len(self.indice.paginas(rel)) > 1 and pag:
            return f"{d.nombre} · {pag['nombre']}"
        return d.nombre
