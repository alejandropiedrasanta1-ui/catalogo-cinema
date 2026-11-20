"""Pantalla Ajustes: carpetas, PhotoCraft, calidad, tema y qué PSD se muestran en el catálogo."""
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF, InfoBar, InfoBarPosition,
                            ListWidget, PushButton, SpinBox, TransparentPushButton, StrongBodyLabel, Theme, TitleLabel, setTheme)

import ampliar
import config
import envio
import estilo
import photocraft
import rutas


def aplicar_tema(nombre):
    setTheme({"Claro": Theme.LIGHT, "Sistema": Theme.AUTO}.get(nombre, Theme.DARK))


class Fila(QWidget):
    def __init__(self, titulo, descripcion, derecha):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(StrongBodyLabel(titulo))
        self.desc = CaptionLabel(descripcion)
        self.desc.setWordWrap(True)
        self.desc.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        textos.addWidget(self.desc)
        lay.addLayout(textos, 1)
        for w in derecha:
            lay.addWidget(w)


class AjustesInterface(QWidget):
    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.setObjectName("ajustes")
        self.estado = estado
        cfg = estado.cfg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 16)
        lay.setSpacing(12)
        lay.addWidget(TitleLabel("Ajustes"))

        t = estilo.Tarjeta(nivel=1)
        tl = QVBoxLayout(t)
        tl.setContentsMargins(18, 10, 18, 10)
        b_cat = PushButton(FIF.FOLDER, "Cambiar…")
        b_cat.clicked.connect(self._carpeta_catalogo)
        self.f_cat = Fila("Carpeta del catálogo", cfg["carpeta_catalogo"], [b_cat])
        b_sal = PushButton(FIF.FOLDER, "Cambiar…")
        b_sal.clicked.connect(self._carpeta_salida)
        self.f_sal = Fila("Carpeta de los envíos", cfg["carpeta_salida"], [b_sal])
        b_pc = PushButton(FIF.APPLICATION, "Elegir…")
        b_pc.clicked.connect(self._photocraft)
        self.f_pc = Fila("PhotoCraft (photocraft-cli)", self._texto_pc(), [b_pc])
        self.calidad = SpinBox()
        self.calidad.setRange(80, 100)
        self.calidad.setValue(int(cfg.get("calidad_jpg", 95)))
        self.calidad.valueChanged.connect(lambda v: self._poner("calidad_jpg", v))
        f_cal = Fila("Calidad JPG", "95 (recomendado): sin pérdida visible. Los JPG se guardan con color completo (4:4:4).", [self.calidad])
        self.tema = ComboBox()
        self.tema.addItems(["Oscuro", "Claro", "Sistema"])
        self.tema.setCurrentText(cfg.get("tema", "Oscuro"))
        self.tema.currentTextChanged.connect(self._tema)
        f_tema = Fila("Tema", "Apariencia del programa.", [self.tema])
        b_mini = PushButton(FIF.SYNC, "Rehacer todas")
        b_mini.clicked.connect(self._rehacer_miniaturas)
        f_mini = Fila("Miniaturas", "Se rehacen solas cuando cambia un PSD. Úsalo solo si alguna se ve mal.",
                      [b_mini])
        self.b_hd = PushButton(FIF.SPEED_HIGH, "Pulir todo")
        self.b_hd.clicked.connect(self._preparar_hd)
        self.b_hd_abrir = TransparentPushButton(FIF.FOLDER, "Abrir")
        self.b_hd_abrir.clicked.connect(lambda: rutas.abrir(self._carpeta_hd()) if os.path.isdir(
            self._carpeta_hd()) else None)
        self.f_hd = Fila("Pulir todo el catálogo (IA)",
                         "Amplía con IA todas las páginas (calidad de Enviar) y deja la carpeta «CATALOGO HD» con "
                         "cada página en JPG y un PDF por sección. Tarda unos minutos, en segundo plano; después "
                         "enviar es instantáneo. Los PSD no se tocan." if ampliar.disponible() else
                         "No se encontró el ampliador IA (recursos\\realesrgan): se usará ampliación normal.",
                         [self.b_hd, self.b_hd_abrir])
        for f in (self.f_cat, self.f_sal, self.f_pc, f_cal, self.f_hd, f_tema, f_mini):
            tl.addWidget(f)
        lay.addWidget(t)

        t2 = estilo.Tarjeta(nivel=1)
        t2l = QVBoxLayout(t2)
        t2l.setContentsMargins(18, 12, 18, 12)
        t2l.addWidget(StrongBodyLabel("PSD que se muestran en el catálogo"))
        ayuda = CaptionLabel("Desmarca los que no quieras ver (versiones viejas, borradores…).")
        ayuda.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        t2l.addWidget(ayuda)
        self.lista = ListWidget()
        self.lista.itemChanged.connect(self._excluir)
        t2l.addWidget(self.lista, 1)
        lay.addWidget(t2, 1)
        version = CaptionLabel(f"{rutas.APP} {rutas.VERSION} · datos en {rutas.DATOS}")
        version.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        lay.addWidget(version)
        estado.catalogo_cambiado.connect(self._llenar)

    def _texto_pc(self):
        exe = self.estado.cfg.get("photocraft_cli") or photocraft.buscar_photocraft()
        return exe or "No encontrado: instala PhotoCraft o indica dónde está."

    def _poner(self, clave, valor):
        self.estado.cfg[clave] = valor
        config.guardar(self.estado.cfg)

    def _aviso(self, texto):
        InfoBar.success("Listo", texto, parent=self.window(), duration=2500, position=InfoBarPosition.TOP_RIGHT)

    def _carpeta_catalogo(self):
        c = QFileDialog.getExistingDirectory(self, "Carpeta del catálogo", self.estado.cfg["carpeta_catalogo"])
        if c:
            self._poner("carpeta_catalogo", c)
            self.f_cat.desc.setText(c)
            self.estado.configurar_sesion()
            self.estado.recargar()

    def _carpeta_salida(self):
        c = QFileDialog.getExistingDirectory(self, "Carpeta de los envíos", self.estado.cfg["carpeta_salida"])
        if c:
            self._poner("carpeta_salida", c)
            self.f_sal.desc.setText(c)

    def _photocraft(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Ubicar photocraft-cli", "",
                                                 "photocraft-cli (photocraft-cli*);;Todos (*)")
        if archivo:
            self._poner("photocraft_cli", archivo)
            self.f_pc.desc.setText(archivo)
            self.estado.configurar_sesion()
            self.estado.preparar_miniaturas()

    def _tema(self, nombre):
        self._poner("tema", nombre)
        aplicar_tema(nombre)

    def _carpeta_hd(self):
        return os.path.join(self.estado.cfg["carpeta_catalogo"], "CATALOGO HD")

    def _preparar_hd(self):
        e = self.estado
        nivel = e.cfg.get("calidad_envio", "alta")
        if nivel == "normal":
            nivel = "alta"
        secciones = {s: e.visibles(s) for s in e.secciones if e.visibles(s)}
        destino, calidad = self._carpeta_hd(), e.cfg.get("calidad_jpg", 95)
        self.b_hd.setEnabled(False)
        self.f_hd.desc.setText("Preparando… puedes seguir usando el programa.")

        def avisar(hechos, total, texto):
            e.trabajador.principal(lambda: (
                self.f_hd.desc.setText(f"{hechos}/{total} · {texto}"),
                e.progreso.emit(f"Alta calidad (IA): {texto}", hechos, total) if hechos < total else
                e.progreso.emit("", 0, 0)))

        def listo(carpeta):
            self.b_hd.setEnabled(True)
            e.progreso.emit("", 0, 0)
            self.f_hd.desc.setText(f"Listo: todo el catálogo en alta calidad ({nivel}) en {carpeta}. "
                                   "Enviar ya es instantáneo.")

        def fallo(err):
            self.b_hd.setEnabled(True)
            self.f_hd.desc.setText(f"Se detuvo: {err}")
            e.progreso.emit("", 0, 0)
        e.trabajador.enviar(lambda: envio.catalogo_hd(e.sesion, e.indice, e.ediciones, e.docs, secciones, destino,
                                                      nivel, calidad, avisar),
                            listo=listo, fallo=fallo)

    def _rehacer_miniaturas(self):
        e = self.estado
        e.trabajador.cancelar("mini")
        e.indice.olvidar()
        e._pix.clear()
        e.recargar()
        self._aviso("Se están rehaciendo las miniaturas.")

    def _llenar(self):
        self.lista.blockSignals(True)
        self.lista.clear()
        excluir = set(self.estado.cfg.get("excluir") or [])
        for docs in self.estado.secciones.values():
            for d in docs:
                it = QListWidgetItem(d.rel)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked if d.rel in excluir else Qt.Checked)
                self.lista.addItem(it)
        self.lista.blockSignals(False)

    def _excluir(self, it):
        excluir = set(self.estado.cfg.get("excluir") or [])
        if it.checkState() == Qt.Checked:
            excluir.discard(it.text())
        else:
            excluir.add(it.text())
        self._poner("excluir", sorted(excluir))
        self.estado.catalogo_cambiado.emit()
        self.estado.preparar_miniaturas()
