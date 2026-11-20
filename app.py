"""Ventana principal: barra lateral (Catálogo, Editor, Enviar, Ajustes) con el mismo estilo que Comprobantes."""
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QRectF, Qt, QTimer, QTranslator
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (FluentIcon as FIF, FluentTranslator, MSFluentWindow, NavigationItemPosition,
                            NavigationWidget, setFontFamilies, setThemeColor)

import config
import estilo
import rutas
from estado import Estado
from ui_ajustes import AjustesInterface, aplicar_tema
from ui_catalogo import CatalogoInterface
from ui_editor import EditorInterface
from ui_envio import EnvioInterface

COLOR_MARCA = "#e0262b"
ES_MAC = sys.platform == "darwin"
IDEAL = (1440, 920)
MINIMO = (900, 600)


class _Marca(NavigationWidget):
    def __init__(self, parent=None):
        super().__init__(isSelectable=False, parent=parent)
        self.pm = QPixmap(str(rutas.recurso("recursos/icono.png")))
        self.setFixedSize(64, 62)
        self.setToolTip("Catálogo · Cinema Productions")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        lado = 38
        r = QRectF((self.width() - lado) / 2, (self.height() - lado) / 2, lado, lado)
        p.setPen(Qt.NoPen)
        for i, a in enumerate((26, 14, 7)):
            p.setBrush(estilo.alfa(estilo.ROJO, a))
            g = 3 + 4 * i
            p.drawRoundedRect(r.adjusted(-g, -g, g, g), 12 + g, 12 + g)
        dpr = self.devicePixelRatioF()
        pm = self.pm.scaled(int(lado * dpr), int(lado * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        p.drawPixmap(r.topLeft(), pm)
        p.end()


class Ventana(MSFluentWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        setThemeColor(QColor(COLOR_MARCA))
        self.setWindowTitle("Catálogo · Cinema Productions")
        self.setWindowIcon(QIcon(str(rutas.recurso("recursos/icono.png"))))
        self.setMicaEffectEnabled(False)
        self.setCustomBackgroundColor(QColor("#FBF0F1"), QColor("#1B0A0F"))
        self.navigationInterface.setSelectedColor(QColor(estilo.ROJO), QColor(estilo.ROJO_CLARO))

        self.estado = Estado(cfg)
        self.catalogo = CatalogoInterface(self.estado, self)
        self.editor = EditorInterface(self.estado, self)
        self.envio = EnvioInterface(self.estado, self)
        self.ajustes = AjustesInterface(self.estado, self)
        self.navigationInterface.addWidget("marca", _Marca(), lambda: self.switchTo(self.catalogo))
        self.addSubInterface(self.catalogo, FIF.LIBRARY, "Catálogo")
        self.addSubInterface(self.editor, FIF.EDIT, "Editor")
        self.addSubInterface(self.envio, FIF.SEND, "Enviar")
        self.addSubInterface(self.ajustes, FIF.SETTING, "Ajustes", position=NavigationItemPosition.BOTTOM)

        self.estado.abrir_editor.connect(self._abrir_editor)
        self.estado.ir_a_envio.connect(lambda: self.switchTo(self.envio))
        self.estado.seleccion_cambiada.connect(self._contar)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._buscar)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._guardar)
        self.ajustar_a_pantalla()
        QTimer.singleShot(0, self.estado.recargar)

    def ajustar_a_pantalla(self):
        zona = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(min(MINIMO[0], zona.width()), min(MINIMO[1], zona.height()))
        ancho = max(self.minimumWidth(), min(IDEAL[0], int(zona.width() * 0.94)))
        alto = max(self.minimumHeight(), min(IDEAL[1], int(zona.height() * 0.94)))
        self.resize(ancho, alto)
        self.move(zona.x() + (zona.width() - ancho) // 2, zona.y() + (zona.height() - alto) // 2)

    def _abrir_editor(self, rel, pid):
        self.switchTo(self.editor)
        self.editor.abrir(rel, pid)

    def _contar(self):
        n = len(self.estado.seleccion)
        item = self.navigationInterface.widget(self.envio.objectName())
        if item is not None:
            item.setText(f"Enviar ({n})" if n else "Enviar")

    def _buscar(self):
        self.switchTo(self.catalogo)
        self.catalogo.buscar.setFocus()
        self.catalogo.buscar.selectAll()

    def _guardar(self):
        if self.stackedWidget.currentWidget() is self.editor and self.editor.hay_cambios():
            self.editor.guardar()

    def closeEvent(self, e):
        if self.editor.hay_cambios():
            self.editor.preguntar_guardar()
        self.estado.cerrar()
        super().closeEvent(e)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    QLocale.setDefault(QLocale(QLocale.Spanish, QLocale.Guatemala))
    traductores = [FluentTranslator(QLocale(QLocale.Spanish, QLocale.Spain)), QTranslator()]
    traductores[1].load("qtbase_es", QLibraryInfo.path(QLibraryInfo.TranslationsPath))
    for tr in traductores:
        app.installTranslator(tr)
    if ES_MAC:
        setFontFamilies([".AppleSystemUIFont", "Helvetica Neue", "PingFang SC"])
    rutas.preparar_carpetas()
    cfg = config.cargar()
    aplicar_tema(cfg.get("tema", "Oscuro"))
    setThemeColor(QColor(COLOR_MARCA))
    ventana = Ventana(cfg)
    ventana.show()
    return app.exec()
