"""Catálogo · Cinema Productions — punto de entrada.

  python catalogo_cinema.py                 abre el programa
  python catalogo_cinema.py --verificar     arma la ventana sin mostrarla
  python catalogo_cinema.py --captura PNG   abre, espera las miniaturas y guarda una captura de la ventana
"""
import sys


def _verificar():
    """Arma la ventana completa sin mostrarla (sirve también en la Mac de GitHub Actions)."""
    import os
    if sys.platform != "darwin":
        # En Mac no: la ventana sin bordes usa la vista nativa de Cocoa y se cae en modo offscreen
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    import app as ventana_app
    import config
    import rutas
    a = QApplication(sys.argv)
    rutas.preparar_carpetas()
    v = ventana_app.Ventana(config.cargar())
    print("OK interfaz:", [v.stackedWidget.widget(i).objectName() for i in range(v.stackedWidget.count())])
    v.estado.cerrar()
    v.close()
    a.quit()
    return 0


def _captura(destino, espera_s=240):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import app as ventana_app
    import config
    import rutas
    a = QApplication(sys.argv)
    rutas.preparar_carpetas()
    cfg = config.cargar()
    ventana_app.aplicar_tema(cfg.get("tema", "Oscuro"))
    v = ventana_app.Ventana(cfg)
    v.show()
    inicio = [0]
    if "--ver" in sys.argv:   # prueba: elige 3 páginas y muestra esa pantalla (catalogo, envio, ajustes…)
        pantalla = sys.argv[sys.argv.index("--ver") + 1]

        def ver():
            items = []
            for s in v.estado.secciones:   # la primera página de cada sección
                for d in v.estado.visibles(s)[:1]:
                    items += [(d.rel, p["id"]) for p in v.estado.indice.paginas(d.rel)[:1]]
            v.estado.agregar(items)
            v.switchTo(getattr(v, pantalla))
        QTimer.singleShot(2500, ver)
    if "--editor" in sys.argv:   # prueba: abre el editor en ese PSD y cambia un texto
        rel = sys.argv[sys.argv.index("--editor") + 1]

        def editar():
            v.estado.abrir_editor.emit(rel, -1)

        def escribir():
            filas = [f for f in v.editor.filas if f.texto is not None]
            if filas:
                filas[0].texto.setPlainText("TEXTO EDITADO")
        QTimer.singleShot(1500, editar)
        QTimer.singleShot(9000, escribir)
        espera_s = 25

    def revisar():
        inicio[0] += 1
        listo = v.estado.trabajador.pendientes() == 0 and inicio[0] > 6 and "--editor" not in sys.argv
        if listo or inicio[0] > espera_s:
            v.grab().save(destino)
            v.close()
            a.quit()
        else:
            QTimer.singleShot(1000, revisar)
    QTimer.singleShot(1000, revisar)
    return a.exec()


if __name__ == "__main__":
    if "--verificar" in sys.argv:
        sys.exit(_verificar())
    if "--captura" in sys.argv:
        sys.exit(_captura(sys.argv[sys.argv.index("--captura") + 1]))
    import app
    sys.exit(app.main())
