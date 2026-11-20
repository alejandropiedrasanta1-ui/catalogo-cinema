"""Pantalla Catálogo (diseño 2026, tema vino): saludo y buscador arriba, secciones en píldoras, un banner
con degradado coral y las páginas en abanico, la cuadrícula de páginas y a la derecha el panel «Tu envío».
Clic en una página = elegirla para el cliente · doble clic = verla en grande · clic derecho = más opciones."""
import math
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (Action, FlowLayout, FluentIcon as FIF, PrimaryPushButton, PushButton, RoundMenu,
                            ScrollArea, SearchLineEdit, StrongBodyLabel, TransparentToolButton)

import estilo

ANCHO_MINI = 210


def transparente(scroll):
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none}")
    scroll.viewport().setStyleSheet("background:transparent")


def letra(px, peso=QFont.Normal, base=None):
    f = QFont(base) if base else QFont()
    f.setPixelSize(px)
    f.setWeight(peso)
    return f


_escaladas = {}


def escalada(pm, ancho, alto, modo):
    """Copia escalada (suave) de un pixmap, guardada en caché: así pasar el mouse o desplazarse no vuelve a
    escalar imágenes grandes en cada cuadro."""
    clave = (pm.cacheKey(), ancho, alto, modo.value)
    esc = _escaladas.get(clave)
    if esc is None:
        if len(_escaladas) > 400:
            _escaladas.clear()
        esc = pm.scaled(ancho, alto, modo, Qt.SmoothTransformation)
        _escaladas[clave] = esc
    return esc


def dibujar_pix(p, pm, caja, radio, cubrir=True):
    """Pinta un pixmap dentro de una caja redondeada (cubrir = llena la caja recortando)."""
    if not pm or pm.isNull():
        return False
    camino = QPainterPath()
    camino.addRoundedRect(caja, radio, radio)
    p.save()
    p.setClipPath(camino)
    modo = Qt.KeepAspectRatioByExpanding if cubrir else Qt.KeepAspectRatio
    dpr = p.device().devicePixelRatioF() if hasattr(p.device(), "devicePixelRatioF") else 1.0
    esc = escalada(pm, int(caja.width() * dpr), int(caja.height() * dpr), modo)
    esc.setDevicePixelRatio(dpr)
    w, h = esc.width() / dpr, esc.height() / dpr
    p.drawPixmap(QPointF(caja.x() + (caja.width() - w) / 2, caja.y() + (caja.height() - h) / 2), esc)
    p.restore()
    return True


class Boton(QWidget):
    """Botón redondo o píldora pintado (blanco sobre el banner, o vidrio)."""
    clicked = Signal()

    def __init__(self, texto="", icono=None, claro=False, parent=None):
        super().__init__(parent)
        self.texto, self.icono, self.claro = texto, icono, claro
        self._encima = False
        self.setCursor(Qt.PointingHandCursor)
        fm = QFontMetrics(letra(13, QFont.DemiBold))
        self.setFixedSize((fm.horizontalAdvance(texto) + (44 if icono else 28)) if texto else 38, 38)

    def enterEvent(self, e):
        self._encima = True
        self.update()

    def leaveEvent(self, e):
        self._encima = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.claro:
            fondo, tinta = QColor(255, 255, 255, 245 if self._encima else 230), QColor("#3A0C16")
        else:
            fondo, tinta = QColor(255, 255, 255, 46 if self._encima else 30), QColor("white")
        p.setPen(Qt.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        x = 14 if self.texto else (r.width() - 16) / 2
        if self.icono:
            self.icono.render(p, QRectF(x, (r.height() - 16) / 2, 16, 16), fill=tinta.name())
            x += 22
        if self.texto:
            p.setPen(tinta)
            p.setFont(letra(13, QFont.DemiBold))
            p.drawText(QRectF(x, 0, r.width() - x, r.height()), Qt.AlignVCenter | Qt.AlignLeft, self.texto)
        p.end()


class Chip(QWidget):
    """Sección en píldora: la activa con el degradado coral, las demás en vidrio granate."""
    clicked = Signal()

    def __init__(self, texto, n, parent=None):
        super().__init__(parent)
        self.texto, self.n, self.activo, self._encima = texto, n, False, False
        self.setCursor(Qt.PointingHandCursor)
        fm = QFontMetrics(letra(13, QFont.DemiBold))
        self.setFixedSize(fm.horizontalAdvance(texto) + (58 if n is not None else 34), 40)

    def poner(self, si):
        self.activo = si
        self.update()

    def enterEvent(self, e):
        self._encima = True
        self.update()

    def leaveEvent(self, e):
        self._encima = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self.activo:
            p.setPen(Qt.NoPen)
            p.setBrush(estilo.degradado(r, estilo.CORAL, estilo.ROJO))
            tinta = QColor("white")
        else:
            p.setPen(QPen(estilo.c("borde2" if self._encima else "borde"), 1))
            p.setBrush(estilo.c("sup2" if self._encima else "sup"))
            tinta = estilo.c("texto2")
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(letra(13, QFont.DemiBold))
        p.setPen(tinta)
        p.drawText(QRectF(17, 0, r.width(), r.height()), Qt.AlignVCenter | Qt.AlignLeft, self.texto)
        if self.n is not None:
            fm = p.fontMetrics()
            b = QRectF(17 + fm.horizontalAdvance(self.texto) + 7, (r.height() - 20) / 2 + 1, 24, 20)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 60) if self.activo else estilo.c("sup3"))
            p.drawRoundedRect(b, 10, 10)
            p.setPen(tinta)
            p.setFont(letra(11, QFont.Bold))
            p.drawText(b, Qt.AlignCenter, str(self.n))
        p.end()


class Heroe(QWidget):
    """Banner de la sección: degradado coral → vino, círculos decorativos, textos y tres páginas en abanico."""

    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.estado = estado
        self.titulo, self.sub, self.paginas = "", "", []
        self.setFixedHeight(250)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(34, 0, 0, 30)
        lay.setSpacing(10)
        self.b_todas = Boton("Elegir todas", FIF.ADD, claro=True)
        self.b_ver = Boton("Ver en grande", FIF.ZOOM_IN)
        lay.addWidget(self.b_todas, 0, Qt.AlignBottom)
        lay.addWidget(self.b_ver, 0, Qt.AlignBottom)
        lay.addStretch(1)

    def poner(self, titulo, sub, paginas):
        self.titulo, self.sub, self.paginas = titulo, sub, paginas
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        camino = QPainterPath()
        camino.addRoundedRect(r, 28, 28)
        p.setClipPath(camino)
        p.fillRect(r, estilo.degradado(r, "#FF7A5C", "#7A1028"))
        p.setPen(Qt.NoPen)   # círculos de luz
        for cx, cy, rad, a in ((0.62, -0.1, 0.42, 26), (0.95, 1.1, 0.35, 30), (0.08, 1.2, 0.3, 18)):
            p.setBrush(QColor(255, 255, 255, a))
            p.drawEllipse(QPointF(r.width() * cx, r.height() * cy), r.height() * rad * 1.6, r.height() * rad * 1.6)
        # textos
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        etiqueta = QRectF(34, 30, 128, 28)
        p.drawRoundedRect(etiqueta, 14, 14)
        p.setPen(QColor("#7A1028"))
        p.setFont(letra(12, QFont.Bold))
        p.drawText(etiqueta, Qt.AlignCenter, "★  CATÁLOGO")
        p.setPen(QColor("white"))
        ancho_txt = max(200, r.width() * 0.5)
        p.setFont(letra(40, QFont.Black))
        fm = p.fontMetrics()
        p.drawText(QRectF(32, 66, ancho_txt, 56), Qt.AlignLeft | Qt.AlignVCenter,
                   fm.elidedText(self.titulo, Qt.ElideRight, int(ancho_txt)))
        p.setPen(QColor(255, 255, 255, 215))
        p.setFont(letra(14, QFont.Medium))
        p.drawText(QRectF(34, 122, ancho_txt, 44), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.sub)
        # páginas en abanico (derecha)
        alto = r.height() * 0.86
        base_x = r.width() - 70
        for i, pm in enumerate(reversed(self.paginas[:3])):
            k = len(self.paginas[:3]) - 1 - i
            ang = (-12, 0, 12)[k] if len(self.paginas) >= 3 else (-8, 8, 0)[k]
            w = alto * 0.72
            cx = base_x - 120 * (2 - k) - w / 2 + 40
            p.save()
            p.translate(cx, r.height() * 0.62)
            p.rotate(ang)
            caja = QRectF(-w / 2, -alto / 2, w, alto)
            for s in range(6, 0, -2):   # sombra
                p.setBrush(QColor(40, 0, 10, 22))
                p.drawRoundedRect(caja.adjusted(-s + 4, -s + 8, s + 4, s + 8), 16 + s, 16 + s)
            p.setBrush(QColor("white"))
            p.drawRoundedRect(caja.adjusted(-5, -5, 5, 5), 18, 18)
            dibujar_pix(p, pm, caja, 14)
            p.restore()
        p.end()


class Miniatura(QWidget):
    """Página: imagen redondeada a sangre, degradado abajo con el nombre, anillo coral y número al elegirla."""

    def __init__(self, estado, rel, pag, parent=None):
        super().__init__(parent)
        self.estado, self.rel, self.pag = estado, rel, pag
        self._t = 0.0
        x, y, w, h = pag["rect"]
        alto = int(min(ANCHO_MINI * 1.5, max(ANCHO_MINI * 0.55, ANCHO_MINI * h / max(w, 1))))
        self.setFixedSize(ANCHO_MINI, alto)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clic: elegir para el cliente · Doble clic: ver en grande · Clic derecho: más")

    def actualizar(self):
        self.update()

    def enterEvent(self, e):
        estilo.animar(self, "_ani", self._t, 1.0, 150, self._poner_t)

    def leaveEvent(self, e):
        estilo.animar(self, "_ani", self._t, 0.0, 220, self._poner_t)

    def _poner_t(self, v):
        self._t = v
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.estado.alternar(self.rel, self.pag["id"])

    def mouseDoubleClickEvent(self, e):
        self.estado.alternar(self.rel, self.pag["id"])   # deshace el clic del doble clic
        VistaGrande(self.estado, self.rel, self.pag["id"], self.window()).exec()

    def contextMenuEvent(self, e):
        m = RoundMenu(parent=self)
        sel = self.estado.seleccionada(self.rel, self.pag["id"])
        m.addAction(Action(FIF.ZOOM_IN, "Ver en grande",
                           triggered=lambda: VistaGrande(self.estado, self.rel, self.pag["id"], self.window()).exec()))
        m.addAction(Action(FIF.EDIT, "Editar esta página",
                           triggered=lambda: self.estado.abrir_editor.emit(self.rel, self.pag["id"])))
        m.addAction(Action(FIF.REMOVE if sel else FIF.ADD, "Quitar del envío" if sel else "Agregar al envío",
                           triggered=lambda: self.estado.alternar(self.rel, self.pag["id"])))
        m.exec(e.globalPos())

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        sel = self.estado.seleccionada(self.rel, self.pag["id"])
        caja = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        radio = 20
        camino = QPainterPath()
        camino.addRoundedRect(caja, radio, radio)
        p.setPen(Qt.NoPen)
        p.setBrush(estilo.c("sup2"))
        p.drawPath(camino)
        pm = self.estado.pixmap(self.rel, self.pag["id"])
        if not dibujar_pix(p, pm, caja, radio):
            p.setPen(estilo.c("texto3"))
            p.setFont(letra(12))
            error = self.estado.indice.de(self.rel).get("error")
            p.drawText(caja, Qt.AlignCenter | Qt.TextWordWrap, "No se pudo abrir" if error else "Preparando…")
        # degradado inferior con el nombre
        p.save()
        p.setClipPath(camino)
        franja = QRectF(caja.left(), caja.bottom() - 74, caja.width(), 74)
        p.fillRect(franja, estilo.degradado(franja, QColor(20, 4, 8, 0), QColor(20, 4, 8, 225), vertical=True))
        if self._t > 0:   # brillo al pasar el mouse
            p.fillRect(caja, QColor(255, 255, 255, int(18 * self._t)))
        p.restore()
        doc = self.estado.docs.get(self.rel)
        varias = len(self.estado.indice.paginas(self.rel)) > 1
        titulo = doc.nombre if doc else ""
        p.setPen(QColor("white"))
        p.setFont(letra(13, QFont.Bold))
        fm = p.fontMetrics()
        p.drawText(QRectF(caja.left() + 14, caja.bottom() - (46 if varias else 34), caja.width() - 28, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, fm.elidedText(titulo, Qt.ElideRight, int(caja.width() - 28)))
        if varias:
            p.setPen(QColor(255, 255, 255, 190))
            p.setFont(letra(11, QFont.Medium))
            p.drawText(QRectF(caja.left() + 14, caja.bottom() - 26, caja.width() - 28, 16),
                       Qt.AlignLeft | Qt.AlignVCenter, self.pag["nombre"])
        # anillo y número
        if sel or self._t > 0:
            p.setBrush(Qt.NoBrush)
            if sel:
                p.setPen(QPen(QColor(estilo.CORAL), 3))
            else:
                p.setPen(QPen(QColor(255, 255, 255, int(70 * self._t)), 1.5))
            p.drawRoundedRect(caja.adjusted(1.5, 1.5, -1.5, -1.5), radio - 1, radio - 1)
        circ = QRectF(caja.right() - 40, caja.top() + 12, 28, 28)
        if sel:
            n = self.estado.seleccion.index((self.rel, self.pag["id"])) + 1
            p.setPen(QPen(QColor("white"), 2))
            p.setBrush(estilo.degradado(circ, estilo.CORAL, estilo.ROJO))
            p.drawEllipse(circ)
            p.setPen(QColor("white"))
            p.setFont(letra(12, QFont.Bold))
            p.drawText(circ, Qt.AlignCenter, str(n))
        elif self._t > 0:
            p.setPen(QPen(QColor(255, 255, 255, int(220 * self._t)), 2))
            p.setBrush(QColor(0, 0, 0, int(70 * self._t)))
            p.drawEllipse(circ)
            p.drawText(circ, Qt.AlignCenter, "+")
        p.end()


class Encabezado(QWidget):
    """Título de sección con «Ver todo ›» a la derecha."""
    ver_todo = Signal()

    def __init__(self, texto, con_enlace=True, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 18, 0, 4)
        t = QLabel(texto)
        t.setFont(letra(20, QFont.Bold))
        t.setStyleSheet(f"color:{estilo.c('texto').name()}")
        lay.addWidget(t)
        lay.addStretch(1)
        if con_enlace:
            enlace = QLabel("<a href='#' style='color:#FF6B57;text-decoration:none;font-weight:600'>Ver todo ›</a>")
            enlace.setStyleSheet(f"color:{estilo.c('texto3').name()}")
            enlace.linkActivated.connect(lambda _: self.ver_todo.emit())
            lay.addWidget(enlace)


class Anillo(QWidget):
    """Anillo de la sección «Tu envío»: cuántas páginas van, con el degradado de la marca."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.n, self.total = 0, 1
        self.setFixedSize(180, 180)

    def poner(self, n, total):
        self.n, self.total = n, max(total, 1)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        p.setPen(Qt.NoPen)   # halo suave
        for i, a in enumerate((16, 10, 6)):
            p.setBrush(estilo.alfa(estilo.CORAL, a))
            p.drawEllipse(r.adjusted(-4 - 4 * i, -4 - 4 * i, 4 + 4 * i, 4 + 4 * i))
        p.setPen(QPen(estilo.c("sup3"), 14, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(estilo.c("sup"))
        p.drawEllipse(r)
        if self.n:
            pen = QPen(Qt.SolidLine)
            pen.setWidth(14)
            pen.setCapStyle(Qt.RoundCap)
            pen.setBrush(estilo.degradado(r, estilo.CORAL, "#C2185B"))
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * min(1.0, self.n / self.total)))
        p.setPen(estilo.c("texto3"))
        p.setFont(letra(11, QFont.Medium))
        p.drawText(r.adjusted(0, -36, 0, 0), Qt.AlignCenter, "Páginas elegidas")
        p.setPen(estilo.c("texto"))
        p.setFont(letra(36, QFont.Black))
        p.drawText(r.adjusted(0, 10, 0, 0), Qt.AlignCenter, str(self.n))
        p.end()


class FilaEnvio(QWidget):
    """Una página elegida en el panel: miniatura, nombre y ✕."""

    def __init__(self, estado, rel, pid, n, parent=None):
        super().__init__(parent)
        self.estado, self.rel, self.pid, self.n = estado, rel, pid, n
        self.setFixedHeight(58)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(56, 0, 2, 0)
        nombre = QLabel(estado.nombre_pagina(rel, pid))
        nombre.setFont(letra(12, QFont.DemiBold))
        nombre.setStyleSheet(f"color:{estilo.c('texto').name()}")
        nombre.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        quitar = TransparentToolButton(FIF.CLOSE)
        quitar.setFixedSize(28, 28)
        quitar.setIconSize(QSize(10, 10))
        quitar.clicked.connect(lambda: estado.quitar([(rel, pid)]))
        lay.addWidget(nombre, 1)
        lay.addWidget(quitar)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        caja = QRectF(4, 5, 38, 48)
        if not dibujar_pix(p, self.estado.pixmap(self.rel, self.pid), caja, 9):
            p.setBrush(estilo.c("sup3"))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(caja, 9, 9)
        b = QRectF(caja.right() - 10, caja.top() - 3, 18, 18)
        p.setPen(Qt.NoPen)
        p.setBrush(estilo.degradado(b, estilo.CORAL, estilo.ROJO))
        p.drawEllipse(b)
        p.setPen(QColor("white"))
        p.setFont(letra(9, QFont.Bold))
        p.drawText(b, Qt.AlignCenter, str(self.n))
        p.end()


class PanelEnvio(estilo.Tarjeta):
    """Columna derecha «Tu envío»: anillo, lista de páginas elegidas y el botón para enviar."""

    def __init__(self, estado, parent=None):
        super().__init__(parent, nivel=1, radio=28)
        self.estado = estado
        self.setFixedWidth(300)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 20, 14, 18)
        lay.setSpacing(10)
        cab = QHBoxLayout()
        t = QLabel("Tu envío")
        t.setFont(letra(20, QFont.Bold))
        t.setStyleSheet(f"color:{estilo.c('texto').name()}")
        limpiar = TransparentToolButton(FIF.DELETE)
        limpiar.setToolTip("Quitar todas")
        limpiar.clicked.connect(lambda: estado.poner_seleccion([]))
        cab.addWidget(t)
        cab.addStretch(1)
        cab.addWidget(limpiar)
        lay.addLayout(cab)
        self.anillo = Anillo()
        lay.addWidget(self.anillo, 0, Qt.AlignHCenter)
        self.ayuda = QLabel()
        self.ayuda.setWordWrap(True)
        self.ayuda.setAlignment(Qt.AlignCenter)
        self.ayuda.setFont(letra(12))
        self.ayuda.setStyleSheet(f"color:{estilo.c('texto3').name()}")
        lay.addWidget(self.ayuda)
        self.scroll = ScrollArea()
        self.scroll.setWidgetResizable(True)
        transparente(self.scroll)
        self.cont = QWidget()
        self.cont.setStyleSheet("background:transparent")
        self.filas = QVBoxLayout(self.cont)
        self.filas.setContentsMargins(0, 0, 4, 0)
        self.filas.setSpacing(2)
        self.filas.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.cont)
        lay.addWidget(self.scroll, 1)
        self.enviar = PrimaryPushButton("Enviar al cliente")
        estilo.boton_principal(self.enviar, FIF.SEND)
        self.enviar.setMinimumHeight(46)
        self.enviar.clicked.connect(estado.ir_a_envio.emit)
        lay.addWidget(self.enviar)
        estado.seleccion_cambiada.connect(self.refrescar)
        estado.miniatura_lista.connect(lambda _: self.refrescar())
        self.refrescar()

    def refrescar(self):
        while self.filas.count():
            it = self.filas.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        sel = self.estado.seleccion
        total = sum(len(self.estado.indice.paginas(d.rel)) for d in self.estado.visibles())
        self.anillo.poner(len(sel), total)
        self.ayuda.setText("Haz clic en las páginas del catálogo para armar el envío de tu cliente."
                           if not sel else f"de {total} páginas del catálogo · se envían en este orden")
        for i, (rel, pid) in enumerate(sel):
            self.filas.addWidget(FilaEnvio(self.estado, rel, pid, i + 1))
        self.enviar.setEnabled(bool(sel))


class VistaGrande(QDialog):
    """La página en grande, con flechas para pasar por las páginas del PSD."""

    def __init__(self, estado, rel, pid, parent=None):
        super().__init__(parent)
        self.estado, self.rel = estado, rel
        self.paginas = [p["id"] for p in estado.indice.paginas(rel)] or [pid]
        self.i = self.paginas.index(pid) if pid in self.paginas else 0
        self.setWindowTitle(estado.docs[rel].nombre if rel in estado.docs else rel)
        self.setStyleSheet(f"QDialog{{background:{estilo.c('fondo').name()}}}")
        zona = self.screen().availableGeometry()
        self.resize(int(zona.width() * 0.6), int(zona.height() * 0.88))
        lay = QVBoxLayout(self)
        self.img = QLabel(alignment=Qt.AlignCenter)
        self.img.setMinimumSize(200, 200)
        lay.addWidget(self.img, 1)
        barra = QHBoxLayout()
        self.ant = TransparentToolButton(FIF.LEFT_ARROW)
        self.sig = TransparentToolButton(FIF.RIGHT_ARROW)
        self.titulo = StrongBodyLabel()
        self.boton_sel = PrimaryPushButton()
        estilo.boton_principal(self.boton_sel)
        editar = PushButton(FIF.EDIT, "Editar")
        cerrar = PushButton("Cerrar")
        self.ant.clicked.connect(lambda: self.mover(-1))
        self.sig.clicked.connect(lambda: self.mover(1))
        self.boton_sel.clicked.connect(self._alternar)
        editar.clicked.connect(self._editar)
        cerrar.clicked.connect(self.accept)
        for w in (self.ant, self.titulo, self.sig):
            barra.addWidget(w)
        barra.addStretch(1)
        for w in (self.boton_sel, editar, cerrar):
            barra.addWidget(w)
        lay.addLayout(barra)
        self.mostrar()

    def pid(self):
        return self.paginas[self.i]

    def mover(self, d):
        self.i = (self.i + d) % len(self.paginas)
        self.mostrar()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Left, Qt.Key_Right):
            self.mover(-1 if e.key() == Qt.Key_Left else 1)
        elif e.key() == Qt.Key_Space:
            self._alternar()
        else:
            super().keyPressEvent(e)

    def _alternar(self):
        self.estado.alternar(self.rel, self.pid())
        self.mostrar()

    def _editar(self):
        self.estado.abrir_editor.emit(self.rel, self.pid())
        self.accept()

    def mostrar(self):
        self.titulo.setText(f"{self.estado.nombre_pagina(self.rel, self.pid())}   ({self.i + 1}/{len(self.paginas)})")
        sel = self.estado.seleccionada(self.rel, self.pid())
        self.boton_sel.setText("Quitar del envío" if sel else "Agregar al envío")
        self._pintar()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._pintar()

    def _pintar(self):
        pm = self.estado.pixmap(self.rel, self.pid(), grande=True)
        if pm and not pm.isNull():
            dpr = self.devicePixelRatioF()
            esc = pm.scaled(int(self.img.width() * dpr), int(self.img.height() * dpr), Qt.KeepAspectRatio,
                            Qt.SmoothTransformation)
            esc.setDevicePixelRatio(dpr)
            self.img.setPixmap(esc)
        else:
            self.img.setText("Preparando…")


class CatalogoInterface(QWidget):
    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.setObjectName("catalogo")
        self.estado = estado
        self.seccion = None
        self.minis = []
        self.chips = {}
        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(24, 18, 20, 18)
        raiz.setSpacing(20)
        col = QVBoxLayout()
        col.setSpacing(14)

        cab = QHBoxLayout()
        hora = datetime.now().hour
        saludo = "Buenos días" if hora < 12 else "Buenas tardes" if hora < 19 else "Buenas noches"
        self.saludo = QLabel(f"<span style='color:{estilo.c('texto3').name()}'>{saludo},</span> "
                             f"<b style='color:{estilo.c('texto').name()}'>CINEMA PRODUCTIONS</b>")
        self.saludo.setFont(letra(19, QFont.DemiBold))
        cab.addWidget(self.saludo)
        cab.addStretch(1)
        self.buscar = SearchLineEdit()
        self.buscar.setPlaceholderText("Buscar PSD o página…")
        self.buscar.setFixedSize(280, 40)
        self.buscar.textChanged.connect(self._filtrar)
        actualizar = TransparentToolButton(FIF.SYNC)
        actualizar.setFixedSize(40, 40)
        actualizar.setToolTip("Volver a leer la carpeta del catálogo")
        actualizar.clicked.connect(estado.recargar)
        cab.addWidget(self.buscar)
        cab.addWidget(actualizar)
        col.addLayout(cab)

        self.fila_chips = QHBoxLayout()
        self.fila_chips.setSpacing(8)
        col.addLayout(self.fila_chips)

        self.prog = QLabel()
        self.prog.setFont(letra(12))
        self.prog.setStyleSheet(f"color:{estilo.c('texto3').name()}")
        self.prog.hide()
        col.addWidget(self.prog)

        self.scroll = ScrollArea()
        self.scroll.setWidgetResizable(True)
        transparente(self.scroll)
        self.contenido = QWidget()
        self.contenido.setStyleSheet("background:transparent")
        self.lista = QVBoxLayout(self.contenido)
        self.lista.setContentsMargins(0, 0, 10, 10)
        self.lista.setSpacing(6)
        self.lista.setAlignment(Qt.AlignTop)
        self.heroe = Heroe(estado)
        self.heroe.b_todas.clicked.connect(self._elegir_todas)
        self.heroe.b_ver.clicked.connect(self._ver_primera)
        self.scroll.setWidget(self.contenido)
        col.addWidget(self.scroll, 1)
        raiz.addLayout(col, 1)

        self.panel = PanelEnvio(estado)
        raiz.addWidget(self.panel)

        estado.catalogo_cambiado.connect(self._rehacer_secciones)
        estado.miniatura_lista.connect(self._mini_lista)
        estado.progreso.connect(self._progreso)
        estado.seleccion_cambiada.connect(self._seleccion)

    # ---- secciones ----
    def _rehacer_secciones(self):
        while self.fila_chips.count():
            it = self.fila_chips.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.chips = {}
        todo = Chip("Todo", None)
        todo.clicked.connect(lambda: self.mostrar(None))
        self.chips[None] = todo
        self.fila_chips.addWidget(todo)
        for s in self.estado.secciones:
            n = sum(len(self.estado.indice.paginas(d.rel)) or 1 for d in self.estado.visibles(s))
            if n:
                c = Chip(s.title(), n)
                c.clicked.connect(lambda s=s: self.mostrar(s))
                self.chips[s] = c
                self.fila_chips.addWidget(c)
        self.fila_chips.addStretch(1)
        self.mostrar(self.seccion if self.seccion in self.estado.secciones else None)

    def mostrar(self, seccion, conservar=False):
        self.seccion = seccion
        for k, c in self.chips.items():
            c.poner(k == seccion)
        self.heroe.setParent(None)
        while self.lista.count():
            it = self.lista.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.minis = []
        self.lista.addWidget(self.heroe)
        self._poner_heroe()
        docs = self.estado.visibles(seccion)
        grupos = {}
        for d in docs:
            grupos.setdefault(d.seccion, []).append(d)
        for s, ds in grupos.items():
            enc = Encabezado(s.title() if seccion is None else "Páginas", con_enlace=seccion is None)
            enc.ver_todo.connect(lambda s=s: self.mostrar(s))
            self.lista.addWidget(enc)
            zona = QWidget()
            flujo = FlowLayout(zona, needAni=False)
            flujo.setContentsMargins(0, 0, 0, 0)
            flujo.setHorizontalSpacing(16)
            flujo.setVerticalSpacing(16)
            for d in ds:
                pags = self.estado.indice.paginas(d.rel) or [dict(id=0, nombre="", rect=[0, 0, 1224, 1584])]
                for pag in pags:
                    m = Miniatura(self.estado, d.rel, pag, zona)
                    flujo.addWidget(m)
                    self.minis.append(m)
            zona.flujo = flujo
            self.lista.addWidget(zona)
        if not docs:
            vacio = QLabel("No hay PSD en la carpeta del catálogo. Revisa la carpeta en Ajustes.")
            vacio.setAlignment(Qt.AlignCenter)
            self.lista.addWidget(vacio)
        self._filtrar(self.buscar.text())
        if not conservar:
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(0))

    def _paginas_seccion(self):
        return [(d.rel, p["id"]) for d in self.estado.visibles(self.seccion)
                for p in self.estado.indice.paginas(d.rel)]

    def _poner_heroe(self):
        items = self._paginas_seccion()
        docs = self.estado.visibles(self.seccion)
        titulo = self.seccion.title() if self.seccion else "Catálogo completo"
        sub = (f"{len(docs)} diseños · {len(items)} páginas listas para enviar.\n"
               "Elige las páginas y mándalas en PDF o en imágenes.")
        # tres páginas vistosas repartidas por la sección
        muestra = [items[int(i * (len(items) - 1) / 2)] for i in range(3)] if len(items) >= 3 else items
        pms = [pm for pm in (self.estado.pixmap(*it) for it in dict.fromkeys(muestra)) if pm and not pm.isNull()]
        self.heroe.poner(titulo, sub, pms)

    def _elegir_todas(self):
        items = self._paginas_seccion()
        if items and all(self.estado.seleccionada(*i) for i in items):
            self.estado.quitar(items)
        else:
            self.estado.agregar(items)

    def _ver_primera(self):
        items = self._paginas_seccion()
        if items:
            VistaGrande(self.estado, *items[0], self.window()).exec()

    def _filtrar(self, texto):
        t = texto.lower().strip()
        self.heroe.setVisible(not t)
        for m in self.minis:
            d = self.estado.docs.get(m.rel)
            m.setVisible(not t or (d and (t in d.nombre.lower() or t in d.rel.lower()))
                         or t in m.pag["nombre"].lower())

    def _progreso(self, texto, hechos, total):
        self.prog.setVisible(total > 0)
        if total:
            self.prog.setText(f"⏳  Preparando miniaturas con PhotoCraft… {hechos}/{total}")

    def _mini_lista(self, rel):
        actuales = [m for m in self.minis if m.rel == rel]
        pags = self.estado.indice.paginas(rel)
        if [m.pag["id"] for m in actuales] != [p["id"] for p in pags] or any(
                m.pag["rect"] != p["rect"] for m, p in zip(actuales, pags)):
            self.mostrar(self.seccion, conservar=True)   # cambió la cantidad o el tamaño de las páginas
            return
        for m in actuales:
            m.update()
        self._poner_heroe()

    def _seleccion(self):
        for m in self.minis:
            m.update()
