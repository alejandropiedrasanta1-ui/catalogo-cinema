"""Pantalla Enviar: las páginas elegidas (se ordenan arrastrándolas), nombre del cliente y formato
(PDF y/o imágenes). Al terminar: abrir la carpeta o copiar los archivos para pegarlos en WhatsApp."""
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QMimeData, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CheckBox, ComboBox, FluentIcon as FIF, InfoBar,
                            InfoBarPosition, LineEdit, ListWidget, PrimaryPushButton, ProgressBar, PushButton,
                            SegmentedWidget, StrongBodyLabel, SubtitleLabel, TitleLabel, TransparentPushButton)

import ampliar
import config
import envio
import estilo
from ui_catalogo import dibujar_pix, letra


class Delegado(QStyledItemDelegate):
    """Cada página de la lista como tarjeta: número de orden, miniatura, nombre, sección y tamaño final."""

    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.estado = estado

    def sizeHint(self, opt, idx):
        return QSize(0, 104)

    def paint(self, p, opt, idx):
        datos = idx.data(Qt.UserRole)
        if not datos:
            return
        rel, pid = datos
        e = self.estado
        p.save()
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = QRectF(opt.rect).adjusted(2, 4, -10, -4)
        sel = bool(opt.state & QStyle.State_Selected)
        encima = bool(opt.state & QStyle.State_MouseOver)
        p.setPen(QPen(QColor(estilo.CORAL), 1.6) if sel else QPen(estilo.c("borde"), 1))
        p.setBrush(estilo.c("sup3") if sel else estilo.c("sup2") if encima else estilo.c("sup"))
        p.drawRoundedRect(r, 18, 18)
        # número
        b = QRectF(r.x() + 14, r.center().y() - 15, 30, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(estilo.degradado(b, estilo.CORAL, estilo.ROJO))
        p.drawEllipse(b)
        p.setPen(QColor("white"))
        p.setFont(letra(13, QFont.Bold))
        p.drawText(b, Qt.AlignCenter, str(idx.row() + 1))
        # miniatura
        caja = QRectF(b.right() + 14, r.y() + 9, 64, r.height() - 18)
        if not dibujar_pix(p, e.pixmap(rel, pid), caja, 10):
            p.setBrush(estilo.c("sup3"))
            p.drawRoundedRect(caja, 10, 10)
        # textos
        doc = e.docs.get(rel)
        pag = e.indice.pagina(rel, pid) or {}
        x = caja.right() + 18
        ancho = r.right() - x - 150
        p.setPen(estilo.c("texto"))
        p.setFont(letra(15, QFont.Bold))
        nombre = doc.nombre if doc else rel
        p.drawText(QRectF(x, r.y() + 22, ancho, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(nombre, Qt.ElideRight, int(ancho)))
        sub = (doc.seccion.title() if doc else "") + (
            f"  ·  {pag.get('nombre')}" if len(e.indice.paginas(rel)) > 1 else "")
        p.setPen(estilo.c("texto3"))
        p.setFont(letra(12, QFont.Medium))
        p.drawText(QRectF(x, r.y() + 50, ancho, 20), Qt.AlignLeft | Qt.AlignVCenter, sub)
        # tamaño final (con la calidad elegida)
        if pag.get("rect"):
            nivel = e.cfg.get("calidad_envio", "alta")
            w, h = envio.tamano_final(pag["rect"], nivel)
            hd = envio.factor(pag["rect"], nivel) > 1.001
            texto = f"{w}×{h} px"
            p.setFont(letra(11, QFont.DemiBold))
            tw = p.fontMetrics().horizontalAdvance(texto) + 22
            pill = QRectF(r.right() - tw - 16, r.center().y() - 13, tw, 26)
            if hd:
                p.setBrush(estilo.alfa(estilo.CORAL, 46))
                p.setPen(QColor(estilo.CORAL))
            else:
                p.setBrush(estilo.c("sup3"))
                p.setPen(estilo.c("texto2"))
            p.drawRoundedRect(pill, 13, 13)
            p.drawText(pill, Qt.AlignCenter, texto)
            if hd:
                listo = envio.en_cache(e.indice, e.ediciones, rel, pid, nivel)
                etiqueta = "IA ✓" if listo else "IA"
                hb = QRectF(pill.x() - 58, pill.y(), 52, 26)
                p.setPen(Qt.NoPen)
                p.setBrush(estilo.degradado(hb, estilo.CORAL, estilo.ROJO))
                p.drawRoundedRect(hb, 13, 13)
                p.setPen(QColor("white"))
                p.setFont(letra(11, QFont.Black))
                p.drawText(hb, Qt.AlignCenter, etiqueta)
        p.restore()


class EnvioInterface(QWidget):
    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.setObjectName("envio")
        self.estado = estado
        self.resultado = None
        self._armando = False
        cfg = estado.cfg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 16)
        lay.setSpacing(12)
        lay.addWidget(TitleLabel("Enviar al cliente"))

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(16)
        # lista de páginas
        izq = estilo.Tarjeta(nivel=1)
        il = QVBoxLayout(izq)
        il.setContentsMargins(14, 14, 14, 14)
        self.titulo_lista = SubtitleLabel("Páginas")
        ayuda = CaptionLabel("Arrastra para cambiar el orden. Así quedan en el PDF y en los nombres de las imágenes.")
        ayuda.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        self.lista = QListWidget()
        self.lista.setStyleSheet("QListWidget{background:transparent;border:none;outline:none}"
                                 "QListWidget::item{background:transparent;border:none}")
        self.lista.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.lista.setItemDelegate(Delegado(estado, self.lista))
        self.lista.setMouseTracking(True)
        self.lista.setSpacing(2)
        self.lista.setDragDropMode(QAbstractItemView.InternalMove)
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.model().rowsMoved.connect(self._reordenado)
        botones = QHBoxLayout()
        quitar = PushButton(FIF.DELETE, "Quitar")
        limpiar = TransparentPushButton(FIF.CLOSE, "Quitar todas")
        agregar = TransparentPushButton(FIF.ADD, "Agregar más desde el catálogo")
        quitar.clicked.connect(self._quitar)
        limpiar.clicked.connect(lambda: estado.poner_seleccion([]))
        agregar.clicked.connect(lambda: self.window().switchTo(self.window().catalogo))
        botones.addWidget(quitar)
        botones.addWidget(limpiar)
        botones.addStretch(1)
        botones.addWidget(agregar)
        il.addWidget(self.titulo_lista)
        il.addWidget(ayuda)
        il.addWidget(self.lista, 1)
        il.addLayout(botones)
        cuerpo.addWidget(izq, 3)

        # opciones
        der = estilo.Tarjeta(nivel=1)
        dl = QVBoxLayout(der)
        dl.setContentsMargins(18, 16, 18, 16)
        dl.setSpacing(10)
        dl.addWidget(StrongBodyLabel("Cliente"))
        self.cliente = LineEdit()
        self.cliente.setPlaceholderText("Nombre del cliente (para el nombre de la carpeta y del PDF)")
        self.cliente.setClearButtonEnabled(True)
        dl.addWidget(self.cliente)
        dl.addSpacing(6)
        dl.addWidget(StrongBodyLabel("Formato"))
        self.pdf = CheckBox("Un PDF con todas las páginas")
        self.pdf.setChecked(cfg.get("enviar_pdf", True))
        fila = QHBoxLayout()
        self.imgs = CheckBox("Imágenes sueltas en")
        self.imgs.setChecked(cfg.get("enviar_imagenes", True))
        self.formato = ComboBox()
        self.formato.addItems(["JPG", "PNG"])
        self.formato.setCurrentText(cfg.get("formato_imagen", "JPG"))
        fila.addWidget(self.imgs)
        fila.addWidget(self.formato)
        fila.addStretch(1)
        dl.addWidget(self.pdf)
        dl.addLayout(fila)
        for w in (self.pdf, self.imgs):
            w.stateChanged.connect(self._opciones)
        self.formato.currentTextChanged.connect(self._opciones)
        dl.addSpacing(6)
        dl.addWidget(StrongBodyLabel("Calidad"))
        self.nivel = SegmentedWidget()
        for clave, texto in (("normal", "Normal"), ("alta", "Alta ★"), ("maxima", "Máxima")):
            self.nivel.addItem(clave, texto, lambda c=clave: self._poner_nivel(c))
        self.nivel.setCurrentItem(cfg.get("calidad_envio", "alta"))
        self.nivel_ayuda = CaptionLabel()
        self.nivel_ayuda.setWordWrap(True)
        self.nivel_ayuda.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        dl.addWidget(self.nivel)
        dl.addWidget(self.nivel_ayuda)
        self._ayuda_nivel()
        dl.addSpacing(6)
        dl.addWidget(StrongBodyLabel("Se guarda en"))
        self.carpeta = CaptionLabel()
        self.carpeta.setWordWrap(True)
        cambiar = TransparentPushButton(FIF.FOLDER, "Cambiar carpeta…")
        cambiar.clicked.connect(self._cambiar_carpeta)
        dl.addWidget(self.carpeta)
        dl.addWidget(cambiar, 0, Qt.AlignLeft)
        dl.addStretch(1)
        self.progreso = ProgressBar()
        self.progreso.hide()
        self.estado_lbl = CaptionLabel("")
        self.generar = PrimaryPushButton("Generar archivos")
        estilo.boton_principal(self.generar, FIF.SEND)
        self.generar.setMinimumHeight(40)
        self.generar.clicked.connect(self._generar)
        dl.addWidget(self.estado_lbl)
        dl.addWidget(self.progreso)
        dl.addWidget(self.generar)

        self.listo = QWidget()
        ll = QVBoxLayout(self.listo)
        ll.setContentsMargins(0, 8, 0, 0)
        self.listo_lbl = BodyLabel()
        self.listo_lbl.setWordWrap(True)
        ll.addWidget(self.listo_lbl)
        fila2 = QHBoxLayout()
        abrir = PushButton(FIF.FOLDER, "Abrir carpeta")
        copiar = PushButton(FIF.COPY, "Copiar archivos")
        copiar.setToolTip("Copia los archivos: pégalos (Ctrl+V) en WhatsApp, correo o una memoria")
        self.ver_pdf = PushButton(FIF.DOCUMENT, "Abrir PDF")
        abrir.clicked.connect(lambda: self.resultado and self._abrir(self.resultado["carpeta"]))
        copiar.clicked.connect(self._copiar)
        self.ver_pdf.clicked.connect(lambda: self.resultado and self.resultado["pdf"] and self._abrir(self.resultado["pdf"]))
        fila2.addWidget(abrir)
        fila2.addWidget(copiar)
        fila2.addWidget(self.ver_pdf)
        ll.addLayout(fila2)
        self.listo.hide()
        dl.addWidget(self.listo)
        der.setMinimumWidth(360)
        cuerpo.addWidget(der, 2)
        lay.addLayout(cuerpo, 1)

        estado.seleccion_cambiada.connect(self._llenar)
        estado.miniatura_lista.connect(lambda _: self._llenar())
        self._llenar()
        self._opciones()

    def _opciones(self):
        cfg = self.estado.cfg
        cfg.update(enviar_pdf=self.pdf.isChecked(), enviar_imagenes=self.imgs.isChecked(),
                   formato_imagen=self.formato.currentText())
        config.guardar(cfg)
        self.formato.setEnabled(self.imgs.isChecked())
        self.carpeta.setText(cfg["carpeta_salida"])
        self._habilitar()

    AYUDAS = {
        "normal": "Tamaño original de cada PSD. Rápido y liviano, pero se pixelea al hacer mucho zoom.",
        "alta": "Recomendada. Cada página se amplía con IA a 4400 px o más: textos, logos, precios y fotos "
                "nítidos al hacer zoom en el celular.",
        "maxima": "Zoom extremo o impresión grande: IA a 6600 px o más. Archivos más pesados.",
    }

    def _poner_nivel(self, clave):
        self.estado.cfg["calidad_envio"] = clave
        config.guardar(self.estado.cfg)
        self._ayuda_nivel()
        self.lista.viewport().update()

    def _ayuda_nivel(self):
        e = self.estado
        nivel = e.cfg.get("calidad_envio", "alta")
        texto = self.AYUDAS.get(nivel, "")
        if not ampliar.disponible() and nivel != "normal":
            texto += "\n⚠ No se encontró el ampliador IA: se usará una ampliación normal."
        if e.seleccion:
            seg = envio.segundos_estimados(e.indice, e.ediciones, e.seleccion, nivel)
            texto += f"\nTiempo estimado: {'menos de 1 min' if seg < 60 else f'≈ {round(seg / 60)} min'}"
            texto += " (lo ya preparado sale al instante)."
        self.nivel_ayuda.setText(texto)

    def _habilitar(self):
        self.generar.setEnabled(bool(self.estado.seleccion) and (self.pdf.isChecked() or self.imgs.isChecked())
                                and not self.progreso.isVisible())

    def _cambiar_carpeta(self):
        c = QFileDialog.getExistingDirectory(self, "Carpeta para los envíos", self.estado.cfg["carpeta_salida"])
        if c:
            self.estado.cfg["carpeta_salida"] = c
            config.guardar(self.estado.cfg)
            self._opciones()

    # ---- lista ----
    def _llenar(self):
        self._armando = True
        self.lista.clear()
        for rel, pid in self.estado.seleccion:
            it = QListWidgetItem(self.estado.nombre_pagina(rel, pid))
            it.setData(Qt.UserRole, (rel, pid))
            it.setSizeHint(QSize(0, 104))
            self.lista.addItem(it)
        n = len(self.estado.seleccion)
        self.titulo_lista.setText(f"Páginas ({n})" if n else "Páginas")
        self._armando = False
        self._habilitar()
        self._ayuda_nivel()

    def _reordenado(self, *args):
        if self._armando:
            return
        orden = [self.lista.item(i).data(Qt.UserRole) for i in range(self.lista.count())]
        self.estado.seleccion = [tuple(o) for o in orden]
        self.estado.seleccion_cambiada.emit()

    def _quitar(self):
        items = [tuple(it.data(Qt.UserRole)) for it in self.lista.selectedItems()]
        if items:
            self.estado.quitar(items)

    # ---- generar ----
    def _generar(self):
        if self.window().editor.hay_cambios():
            self.window().editor.preguntar_guardar()
        e = self.estado
        items = list(e.seleccion)
        destino = envio.carpeta_envio(e.cfg["carpeta_salida"], self.cliente.text())
        cliente = self.cliente.text()
        pdf, imgs, formato = self.pdf.isChecked(), self.imgs.isChecked(), self.formato.currentText()
        calidad = e.cfg.get("calidad_jpg", 95)
        nivel = e.cfg.get("calidad_envio", "alta")
        self.listo.hide()
        self.progreso.setMaximum(len(items))
        self.progreso.setValue(0)
        self.progreso.show()
        self._habilitar()

        def avisar(hechos, total, texto):
            e.trabajador.principal(lambda: (self.progreso.setValue(hechos), self.estado_lbl.setText(texto)))

        def trabajo():
            return envio.exportar(e.sesion, e.indice, e.ediciones, e.docs, items, destino, cliente, pdf, imgs,
                                  formato, calidad, avisar, nivel)
        e.trabajador.enviar(trabajo, listo=self._terminado, fallo=self._fallo, urgente=True)

    def _terminado(self, r):
        self.resultado = r
        self.progreso.hide()
        self.estado_lbl.setText("")
        partes = []
        if r["pdf"]:
            partes.append("1 PDF")
        if r["imagenes"]:
            partes.append(f"{len(r['imagenes'])} imágenes")
        self.listo_lbl.setText(f"✓ Listo: {' y '.join(partes)} en\n{r['carpeta']}")
        self.ver_pdf.setVisible(bool(r["pdf"]))
        self.listo.show()
        self._habilitar()
        self.lista.viewport().update()
        self._ayuda_nivel()
        InfoBar.success("Archivos listos", "Copia los archivos y pégalos en WhatsApp, o abre la carpeta.",
                        parent=self.window(), duration=4000, position=InfoBarPosition.TOP_RIGHT)

    def _fallo(self, err):
        self.progreso.hide()
        self.estado_lbl.setText("")
        self._habilitar()
        InfoBar.error("No se pudo generar", str(err), parent=self.window(), duration=8000,
                      position=InfoBarPosition.TOP_RIGHT)

    def _archivos(self):
        r = self.resultado or {}
        return ([r["pdf"]] if r.get("pdf") else []) + list(r.get("imagenes") or [])

    def _copiar(self):
        archivos = [str(Path(a).resolve()) for a in self._archivos()]
        if not archivos:
            return
        datos = QMimeData()
        datos.setUrls([QUrl.fromLocalFile(a) for a in archivos])
        QApplication.clipboard().setMimeData(datos)
        InfoBar.success("Copiado", f"{len(archivos)} archivo(s). Pégalos con {'⌘V' if sys.platform == 'darwin' else 'Ctrl+V'} en WhatsApp o en una carpeta.",
                        parent=self.window(), duration=3000, position=InfoBarPosition.TOP_RIGHT)

    @staticmethod
    def _abrir(ruta):
        ruta = str(ruta)
        if sys.platform.startswith("win"):
            os.startfile(ruta)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
