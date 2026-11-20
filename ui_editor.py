"""Pantalla Editor: abre un PSD del catálogo, muestra las capas de la página elegida (textos editables, fotos
que se pueden cambiar y el ojo para mostrar u ocultar) y la vista en vivo dibujada por PhotoCraft.
Los cambios no tocan el PSD original: se guardan en ediciones.json y se aplican al exportar."""
import copy
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF, IndeterminateProgressBar,
                            InfoBar, InfoBarPosition, MessageBox, PlainTextEdit, PrimaryPushButton, PushButton,
                            ScrollArea, SearchLineEdit, SegmentedWidget, StrongBodyLabel, TitleLabel,
                            TransparentPushButton, TransparentToolButton)

import catalogo
import config
import envio
import estilo
import rutas
from ui_catalogo import transparente

LADO_VISTA = 2048
TIPOS = {"Type": "Texto", "Smart Object": "Imagen", "Pixel": "Imagen", "Shape": "Forma", "Group": "Grupo"}


def ajustar_foto(origen, ancho, alto):
    """Recorta la foto al mismo formato que el hueco (tipo «cubrir») y la guarda en la carpeta de imágenes."""
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(origen)).convert("RGB")
    if ancho > 0 and alto > 0:
        objetivo = ancho / alto
        w, h = im.size
        if w / h > objetivo:
            nw = int(h * objetivo)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w / objetivo)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im.thumbnail((3000, 3000))
    rutas.IMAGENES.mkdir(parents=True, exist_ok=True)
    destino = rutas.IMAGENES / f"{uuid.uuid4().hex[:12]}.jpg"
    im.save(destino, "JPEG", quality=95)
    return str(destino)


class FilaCapa(QWidget):
    def __init__(self, editor, capa, nivel):
        super().__init__()
        self.editor, self.capa = editor, capa
        self.lid = str(capa["id"])
        self.tipo = capa.get("kind", "")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(nivel * 14, 2, 4, 2)
        lay.setSpacing(4)
        fila = QHBoxLayout()
        fila.setSpacing(6)
        self.ojo = TransparentToolButton(FIF.VIEW)
        self.ojo.setFixedSize(30, 30)
        self.ojo.setToolTip("Mostrar u ocultar esta capa")
        self.ojo.clicked.connect(self._alternar_visible)
        self.nombre = BodyLabel(capa.get("name") or "")
        self.nombre.setWordWrap(False)
        self.nombre.setMinimumWidth(40)
        tipo = CaptionLabel(TIPOS.get(self.tipo, self.tipo))
        tipo.setTextColor(estilo.c("texto3"), estilo.c("texto3"))
        fila.addWidget(self.ojo)
        fila.addWidget(self.nombre, 1)
        fila.addWidget(tipo)
        lay.addLayout(fila)

        self.texto = None
        self.foto = self.foto_orig = None
        if self.tipo == "Type":
            self.original = (capa.get("text") or {}).get("text", "")
            self.texto = PlainTextEdit()
            self.texto.setPlainText(editor.ed["textos"].get(self.lid, self.original))
            self.texto.textChanged.connect(self._texto_cambio)
            self._alto_texto()
            lay.addWidget(self.texto)
        elif self.tipo == "Smart Object":
            botones = QHBoxLayout()
            botones.setContentsMargins(36, 0, 0, 0)
            self.foto = PushButton(FIF.PHOTO, "Cambiar imagen…")
            self.foto.clicked.connect(self._cambiar_foto)
            self.foto_orig = TransparentPushButton(FIF.RETURN, "Original")
            self.foto_orig.clicked.connect(self._foto_original)
            botones.addWidget(self.foto)
            botones.addWidget(self.foto_orig)
            botones.addStretch(1)
            lay.addLayout(botones)
        self.refrescar()

    def visible(self):
        return self.editor.ed["visibles"].get(self.lid, bool(self.capa.get("visible", True)))

    def refrescar(self):
        vis = self.visible()
        self.ojo.setIcon(FIF.VIEW if vis else FIF.HIDE)
        self.nombre.setEnabled(vis)
        if self.foto_orig:
            self.foto_orig.setVisible(self.lid in self.editor.ed["imagenes"])
        cambiada = (self.lid in self.editor.ed["textos"] or self.lid in self.editor.ed["imagenes"]
                    or self.lid in self.editor.ed["visibles"])
        f = self.nombre.font()
        f.setBold(cambiada)
        self.nombre.setFont(f)

    def _alto_texto(self):
        lineas = max(1, self.texto.toPlainText().count("\n") + 1)
        self.texto.setFixedHeight(16 + 21 * min(lineas, 8))

    def _texto_cambio(self):
        t = self.texto.toPlainText()
        if t == self.original:
            self.editor.ed["textos"].pop(self.lid, None)
            self.editor.ed["originales"].pop(self.lid, None)
        else:
            self.editor.ed["textos"][self.lid] = t
            self.editor.ed["originales"][self.lid] = self.original   # para cambiar solo las letras editadas
        self._alto_texto()
        self.refrescar()
        self.editor.cambio()

    def _alternar_visible(self):
        nuevo = not self.visible()
        if nuevo == bool(self.capa.get("visible", True)):
            self.editor.ed["visibles"].pop(self.lid, None)
        else:
            self.editor.ed["visibles"][self.lid] = nuevo
        self.refrescar()
        self.editor.cambio()

    def _cambiar_foto(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Elegir imagen", str(Path.home() / "Pictures"),
                                                 "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)")
        if not archivo:
            return
        b = self.capa.get("bounds") or [0, 0, 0, 0]
        if isinstance(b, str):
            b = [float(v) for v in b.split()]
        try:
            ruta = ajustar_foto(archivo, b[2], b[3])
        except Exception as e:
            self.editor.aviso(f"No se pudo leer la imagen: {e}", error=True)
            return
        self.editor.ed["imagenes"][self.lid] = ruta
        self.editor.ed["nombres"][self.lid] = self.capa.get("name") or ""
        self.refrescar()
        self.editor.cambio()

    def _foto_original(self):
        self.editor.ed["imagenes"].pop(self.lid, None)
        self.refrescar()
        self.editor.cambio()

    def coincide(self, filtro, texto):
        if filtro == "textos" and self.tipo != "Type":
            return False
        if filtro == "fotos" and self.tipo != "Smart Object":
            return False
        t = texto.lower()
        return not t or t in (self.capa.get("name") or "").lower() or (
            self.texto is not None and t in self.texto.toPlainText().lower())


class EditorInterface(QWidget):
    def __init__(self, estado, parent=None):
        super().__init__(parent)
        self.setObjectName("editor")
        self.estado = estado
        self.rel = None
        self.pid = None
        self.info = None
        self.ed = config.Ediciones().de("")   # vacía
        self.guardada = copy.deepcopy(self.ed)
        self.filas = []
        self.filtro = "textos"
        self.n_vista = 0
        self.pm = None
        self._llenando = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 16)
        lay.setSpacing(12)
        cab = QHBoxLayout()
        cab.addWidget(TitleLabel("Editor"))
        cab.addSpacing(12)
        self.combo_doc = ComboBox()
        self.combo_doc.setMinimumWidth(300)
        self.combo_doc.currentIndexChanged.connect(self._doc_elegido)
        self.combo_pag = ComboBox()
        self.combo_pag.setMinimumWidth(140)
        self.combo_pag.currentIndexChanged.connect(self._pag_elegida)
        cab.addWidget(self.combo_doc)
        cab.addWidget(self.combo_pag)
        cab.addStretch(1)
        self.sin_guardar = CaptionLabel("● Cambios sin guardar")
        self.sin_guardar.setTextColor(estilo.tinta(estilo.AMBAR), estilo.tinta(estilo.AMBAR))
        self.sin_guardar.hide()
        cab.addWidget(self.sin_guardar)
        lay.addLayout(cab)

        acciones = QHBoxLayout()
        self.b_guardar = PrimaryPushButton("Guardar cambios")
        estilo.boton_principal(self.b_guardar, FIF.SAVE)
        self.b_guardar.setToolTip("Guarda los cambios de este PSD: se usan en el catálogo y al enviar")
        self.b_descartar = PushButton(FIF.CANCEL, "Descartar")
        self.b_original = PushButton(FIF.HISTORY, "Volver al original")
        self.b_envio = PushButton(FIF.ADD, "Agregar página al envío")
        self.b_exportar = PushButton(FIF.SAVE_AS, "Exportar página…")
        self.b_psd = PushButton(FIF.DOCUMENT, "Guardar copia PSD…")
        self.b_guardar.clicked.connect(self.guardar)
        self.b_descartar.clicked.connect(self._descartar)
        self.b_original.clicked.connect(self._volver_original)
        self.b_envio.clicked.connect(lambda: self.rel and (self.estado.agregar([(self.rel, self.pid)]),
                                                           self.aviso("Página agregada al envío")))
        self.b_exportar.clicked.connect(self._exportar_pagina)
        self.b_psd.clicked.connect(self._guardar_psd)
        for b in (self.b_guardar, self.b_descartar, self.b_original):
            acciones.addWidget(b)
        acciones.addStretch(1)
        for b in (self.b_envio, self.b_exportar, self.b_psd):
            acciones.addWidget(b)
        lay.addLayout(acciones)

        division = QSplitter(Qt.Horizontal)
        division.setHandleWidth(10)
        division.setStyleSheet("QSplitter::handle{background:transparent}")
        # panel de capas
        panel = estilo.Tarjeta(nivel=1)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(12, 12, 6, 12)
        self.seg = SegmentedWidget()
        self.seg.addItem("textos", "Textos", lambda: self._filtrar("textos"))
        self.seg.addItem("fotos", "Imágenes", lambda: self._filtrar("fotos"))
        self.seg.addItem("todas", "Todas las capas", lambda: self._filtrar("todas"))
        self.seg.setCurrentItem("textos")
        self.buscar = SearchLineEdit()
        self.buscar.setPlaceholderText("Buscar capa o texto…")
        self.buscar.textChanged.connect(lambda: self._filtrar(self.filtro))
        pl.addWidget(self.seg)
        pl.addWidget(self.buscar)
        self.scroll = ScrollArea()
        self.scroll.setWidgetResizable(True)
        transparente(self.scroll)
        self.capas = QWidget()
        self.capas.setStyleSheet("background:transparent")
        self.capas_lay = QVBoxLayout(self.capas)
        self.capas_lay.setContentsMargins(0, 0, 8, 0)
        self.capas_lay.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.capas)
        pl.addWidget(self.scroll, 1)
        panel.setMinimumWidth(320)
        division.addWidget(panel)
        # vista
        vista = estilo.Tarjeta(nivel=1)
        vl = QVBoxLayout(vista)
        vl.setContentsMargins(12, 12, 12, 12)
        fila = QHBoxLayout()
        self.titulo_vista = StrongBodyLabel("Vista previa")
        self.cargando = IndeterminateProgressBar()
        self.cargando.setFixedWidth(160)
        self.cargando.hide()
        self.estado_vista = CaptionLabel("")
        fila.addWidget(self.titulo_vista)
        fila.addStretch(1)
        fila.addWidget(self.estado_vista)
        fila.addWidget(self.cargando)
        vl.addLayout(fila)
        self.imagen = QLabel(alignment=Qt.AlignCenter)
        self.imagen.setMinimumSize(200, 200)
        self.imagen.setText("Abre un PSD desde el Catálogo (botón «Editar») o elígelo arriba.")
        self.imagen.setWordWrap(True)
        vl.addWidget(self.imagen, 1)
        division.addWidget(vista)
        division.setSizes([420, 700])
        division.setStretchFactor(1, 1)
        lay.addWidget(division, 1)

        self.reloj = QTimer(self, singleShot=True, interval=350, timeout=self._pedir_vista)
        estado.catalogo_cambiado.connect(self._llenar_docs)
        estado.miniatura_lista.connect(self._mini_lista)
        self._botones()

    # ---- avisos ----
    def aviso(self, texto, error=False):
        (InfoBar.error if error else InfoBar.success)(
            "No se pudo" if error else "Listo", texto, parent=self.window(), duration=6000 if error else 2500,
            position=InfoBarPosition.TOP_RIGHT)

    def _botones(self):
        abierto = self.info is not None
        sucio = abierto and self.ed != self.guardada
        self.sin_guardar.setVisible(sucio)
        self.b_guardar.setEnabled(sucio)
        self.b_descartar.setEnabled(sucio)
        self.b_original.setEnabled(abierto and not config.vacia(self.ed))
        for b in (self.b_envio, self.b_exportar, self.b_psd):
            b.setEnabled(abierto)

    def hay_cambios(self):
        return self.info is not None and self.ed != self.guardada

    # ---- documento ----
    def _llenar_docs(self):
        self._llenando = True
        self.combo_doc.clear()
        self.rels = []
        for d in self.estado.visibles():
            self.combo_doc.addItem(f"{d.seccion.title()} · {d.nombre}")
            self.rels.append(d.rel)
        if self.rel in self.rels:
            self.combo_doc.setCurrentIndex(self.rels.index(self.rel))
        else:
            self.combo_doc.setCurrentIndex(-1)
            self.combo_doc.setPlaceholderText("Elige un PSD…")
        self._llenando = False

    def _doc_elegido(self, i):
        if self._llenando or i < 0 or i >= len(self.rels) or self.rels[i] == self.rel:
            return
        self.abrir(self.rels[i])

    def _pag_elegida(self, i):
        if self._llenando or not self.info or i < 0:
            return
        pags = catalogo.paginas_de(self.info)
        if i < len(pags) and pags[i]["id"] != self.pid:
            self.pid = pags[i]["id"]
            self._armar_capas()
            self._pedir_vista(inmediato=True)

    def preguntar_guardar(self):
        """True si se puede seguir (guardó o descartó); False si el usuario canceló."""
        if not self.hay_cambios():
            return True
        m = MessageBox("Cambios sin guardar",
                       f"¿Guardar los cambios de «{self.estado.docs[self.rel].nombre}»?", self.window())
        m.yesButton.setText("Guardar")
        m.cancelButton.setText("Descartar")
        if m.exec():
            self.guardar()
        else:
            self.ed = copy.deepcopy(self.guardada)
        return True

    def abrir(self, rel, pid=None):
        if rel not in self.estado.docs:
            return
        if rel == self.rel and self.info:
            if pid is not None and pid != self.pid:
                pags = [p["id"] for p in catalogo.paginas_de(self.info)]
                if pid in pags:
                    self.combo_pag.setCurrentIndex(pags.index(pid))
            return
        self.preguntar_guardar()
        self.rel, self.pid, self.info = rel, pid, None
        self.ed = self.estado.ediciones.de(rel)
        self.guardada = copy.deepcopy(self.ed)
        if rel in getattr(self, "rels", []):
            self._llenando = True
            self.combo_doc.setCurrentIndex(self.rels.index(rel))
            self._llenando = False
        self._limpiar_capas()
        self.combo_pag.clear()
        self.pm = None
        self.imagen.setPixmap(QPixmap())
        self.imagen.setText("Abriendo el PSD con PhotoCraft…")
        self._ocupado(True, "Abriendo…")
        self._botones()
        ruta = self.estado.docs[rel].ruta
        self.estado.trabajador.enviar(lambda: self.estado.sesion.abrir(ruta),
                                      listo=lambda info, rel=rel: self._abierto(rel, info),
                                      fallo=lambda e, rel=rel: self._fallo_abrir(rel, e), clave="editor-abrir",
                                      urgente=True)

    def _abierto(self, rel, info):
        if rel != self.rel:
            return
        self.info = info
        pags = catalogo.paginas_de(info)
        ids = [p["id"] for p in pags]
        if self.pid not in ids:
            self.pid = ids[0]
        self._llenando = True
        self.combo_pag.clear()
        for p in pags:
            self.combo_pag.addItem(p["nombre"])
        self.combo_pag.setCurrentIndex(ids.index(self.pid))
        self.combo_pag.setVisible(len(pags) > 1)
        self._llenando = False
        self._armar_capas()
        self._botones()
        self._pedir_vista(inmediato=True)

    def _fallo_abrir(self, rel, e):
        if rel != self.rel:
            return
        self._ocupado(False)
        self.imagen.setText(f"No se pudo abrir el PSD.\n\n{e}")
        self.rel = None
        self._botones()

    # ---- capas ----
    def _limpiar_capas(self):
        for f in self.filas:
            f.deleteLater()
        self.filas = []
        while self.capas_lay.count():
            it = self.capas_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _armar_capas(self):
        self._limpiar_capas()
        self.capas.setUpdatesEnabled(False)
        for capa, nivel in catalogo.capas_de_pagina(self.info, self.pid):
            f = FilaCapa(self, capa, nivel)
            self.filas.append(f)
            self.capas_lay.addWidget(f)
        self.vacio = BodyLabel("")
        self.vacio.setWordWrap(True)
        self.capas_lay.addWidget(self.vacio)
        self._filtrar(self.filtro)
        self.capas.setUpdatesEnabled(True)

    def _filtrar(self, filtro):
        self.filtro = filtro
        texto = self.buscar.text()
        n = 0
        for f in self.filas:
            si = f.coincide(filtro, texto)
            f.setVisible(si)
            n += si
        if hasattr(self, "vacio"):
            self.vacio.setText("" if n else ("Esta página no tiene textos editables." if filtro == "textos" else
                                             "Esta página no tiene imágenes que se puedan cambiar."
                                             if filtro == "fotos" else "Nada coincide con la búsqueda."))

    def cambio(self):
        self._botones()
        self.reloj.start()

    # ---- vista en vivo ----
    def _ocupado(self, si, texto=""):
        self.cargando.setVisible(si)
        self.estado_vista.setText(texto)

    def _pedir_vista(self, inmediato=False):
        if not self.info:
            return
        self.reloj.stop()
        self.n_vista += 1
        n = self.n_vista
        ed = copy.deepcopy(self.ed)
        rel, ruta = self.rel, self.estado.docs[self.rel].ruta
        pag = next(p for p in catalogo.paginas_de(self.info) if p["id"] == self.pid)
        self.titulo_vista.setText(self.estado.nombre_pagina(rel, self.pid) if self.estado.indice.pagina(rel, self.pid)
                                  else pag["nombre"])
        ses = self.estado.sesion

        def trabajo():
            ses.abrir(ruta)
            ses.preparar(config.pasos(ed), config.firma(ed))
            ses.pagina(pag["rect"], pag.get("visibles"))
            return ses.dibujar(LADO_VISTA)
        self._ocupado(True, "Dibujando…")
        self.estado.trabajador.enviar(trabajo, listo=lambda png: self._vista_lista(n, rel, png),
                                      fallo=lambda e: self._vista_fallo(n, e), clave="vista", urgente=True)

    def _vista_lista(self, n, rel, png):
        if n != self.n_vista or rel != self.rel or png is None:
            return
        self._ocupado(False)
        pm = QPixmap()
        pm.loadFromData(png)
        self.pm = pm
        self._pintar()

    def _vista_fallo(self, n, e):
        if n != self.n_vista:
            return
        self._ocupado(False)
        self.aviso(str(e), error=True)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._pintar()

    def _pintar(self):
        if not self.pm or self.pm.isNull():
            return
        dpr = self.devicePixelRatioF()
        esc = self.pm.scaled(int(self.imagen.width() * dpr), int(self.imagen.height() * dpr), Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
        esc.setDevicePixelRatio(dpr)
        self.imagen.setPixmap(esc)

    def _mini_lista(self, rel):
        pass

    # ---- acciones ----
    def guardar(self):
        if not self.rel:
            return
        self.estado.ediciones.poner(self.rel, copy.deepcopy(self.ed))
        self.guardada = copy.deepcopy(self.ed)
        self._botones()
        self.estado.preparar_miniaturas(solo=self.rel)
        self.aviso("Cambios guardados. Las miniaturas del catálogo se actualizan solas.")

    def _descartar(self):
        self.ed = copy.deepcopy(self.guardada)
        self._armar_capas()
        self._botones()
        self._pedir_vista(inmediato=True)

    def _volver_original(self):
        m = MessageBox("Volver al original",
                       "Se quitan todos los cambios de este PSD (textos, imágenes y capas).\n"
                       "Queda sin guardar hasta que pulses «Guardar cambios».", self.window())
        m.yesButton.setText("Quitar cambios")
        m.cancelButton.setText("Cancelar")
        if not m.exec():
            return
        self.ed = config.Ediciones().de("")
        self._armar_capas()
        self._botones()
        self._pedir_vista(inmediato=True)

    def _trabajo_guardar(self, destino, recortar):
        ed = copy.deepcopy(self.ed)
        ruta = self.estado.docs[self.rel].ruta
        pag = next(p for p in catalogo.paginas_de(self.info) if p["id"] == self.pid)
        rect, vis = (pag["rect"], pag.get("visibles")) if recortar else (None, None)
        ses, calidad = self.estado.sesion, self.estado.cfg.get("calidad_jpg", 95)
        nivel = self.estado.cfg.get("calidad_envio", "alta")
        ppi = self.info.get("resolution") or 144

        def trabajo():
            ses.abrir(ruta)
            ses.preparar(config.pasos(ed), config.firma(ed))
            if recortar:   # página: en alta calidad (textos re-dibujados si es chica)
                return envio.guardar_pagina(ses, rect, destino, nivel, calidad, ppi, vis)[0]
            ses.pagina(None)
            return ses.guardar(destino, calidad)
        self._ocupado(True, "Guardando en alta calidad…")
        self.estado.trabajador.enviar(trabajo, listo=lambda r: (self._ocupado(False), self.aviso(f"Guardado: {r}")),
                                      fallo=lambda e: (self._ocupado(False), self.aviso(str(e), error=True)),
                                      urgente=True)

    def _exportar_pagina(self):
        if not self.info:
            return
        carpeta = Path(self.estado.cfg["carpeta_salida"])
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = envio.limpio(self.estado.nombre_pagina(self.rel, self.pid).replace(" · ", " - "))
        destino, _ = QFileDialog.getSaveFileName(self, "Exportar página", str(carpeta / f"{nombre}.jpg"),
                                                 "JPG (*.jpg);;PNG (*.png)")
        if destino:
            self._trabajo_guardar(destino, True)

    def _guardar_psd(self):
        if not self.info:
            return
        carpeta = Path(self.estado.cfg["carpeta_salida"])
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = envio.limpio(self.estado.docs[self.rel].nombre + " (editado)")
        destino, _ = QFileDialog.getSaveFileName(self, "Guardar copia PSD (con los cambios)",
                                                 str(carpeta / f"{nombre}.psd"), "Photoshop (*.psd)")
        if destino:
            if Path(destino).resolve() == Path(self.estado.docs[self.rel].ruta).resolve():
                self.aviso("Elige otro nombre: el PSD original no se reemplaza.", error=True)
                return
            self._trabajo_guardar(destino, False)
