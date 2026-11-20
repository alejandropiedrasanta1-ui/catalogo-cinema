# Catálogo · Cinema Productions

Programa de escritorio (mismo estilo que *Comprobantes*: PySide6 + Fluent-Widgets, tema vino) para:

- **Catálogo**: ver todos los PSD de `PROGRAMA\CATALOGO` ordenados por sección (cada carpeta es una
  sección; cada mesa de trabajo del PSD es una página). Clic = elegir página · doble clic = verla en
  grande · clic derecho = editar.
- **Editor**: cambiar textos, reemplazar fotos (smart objects) y mostrar/ocultar capas, con vista en vivo.
  El PSD original **no se modifica**: los cambios se guardan aparte (`ediciones.json`) y se aplican al
  exportar. «Guardar copia PSD…» crea un PSD nuevo con los cambios.
- **Enviar**: ordenar las páginas elegidas y generar un PDF y/o imágenes JPG/PNG para el cliente;
  «Copiar archivos» los deja listos para pegar en WhatsApp.

**Alta calidad (sin pixelarse al hacer zoom):** PhotoCraft dibuja cada página a su tamaño original y
**Real-ESRGAN** (IA, `recursos\realesrgan`, corre en la tarjeta de video, sin internet) la amplía: Alta ≥4400 px,
Máxima ≥6600 px. Lo ampliado queda en caché (`%APPDATA%\...\hd`), así que reenviar es instantáneo. JPG al 95 con
color completo (4:4:4) y PDF sin recomprimir. *Ajustes › Pulir todo* lo hace con todo el catálogo y deja
`CATALOGO HD\<sección>\` (JPG + PDF por sección). No se usa el «Tamaño de imagen» de PhotoCraft: deforma
varios diseños. Los PSD con páginas en grupos «pagina 1, 2…» se separan en páginas.

Motor: **PhotoCraft (ArtCraft)** — `photocraft-cli serve` abre los PSD, aplica los cambios, recorta cada
mesa de trabajo y la dibuja/guarda (`photocraft.py`). Requiere PhotoCraft instalado.

## Abrir

`ABRIR CATALOGO.bat` o `python catalogo_cinema.py`.
La primera vez prepara las miniaturas de todos los PSD (~1-2 min); después solo rehace las que cambian.

## Archivos

- `catalogo_cinema.py` entrada · `app.py` ventana · `estado.py` estado compartido + hilo de trabajo
- `catalogo.py` secciones, páginas, miniaturas · `envio.py` exportar imágenes/PDF
- `photocraft.py` puente con PhotoCraft · `config.py` ajustes y ediciones · `rutas.py` carpetas
- `ui_catalogo.py`, `ui_editor.py`, `ui_envio.py`, `ui_ajustes.py` pantallas · `estilo.py` diseño

Datos del usuario (ajustes, ediciones, miniaturas): `%APPDATA%\Catalogo Cinema Productions`.

## Instalador (Windows)

`empaquetar\CREAR INSTALADOR WINDOWS.bat` → `CATAGOLO COMPLETO\INSTALADOR\Instalar Catalogo Cinema (Windows) X.exe`
(PyInstaller + instalador propio en C#, igual que Comprobantes). Para una versión nueva, sube `VERSION` en `rutas.py`.

## Instalador (Mac Apple Silicon)

`INSTALADOR\Instalar Catalogo Cinema (Mac Apple Silicon) X.dmg`: se abre el .dmg y un doble clic en «Instalar Catalogo»
lo copia a Aplicaciones, lo fija en el Dock, abre el programa, se cierra y expulsa el disco (si ya está esa versión,
solo lo abre). Si macOS no lo deja abrir la primera vez: Ajustes › Privacidad y seguridad › «Abrir igualmente».
En la Mac también hacen falta PhotoCraft y los PSD: la carpeta del catálogo es `Documentos/Catalogo Cinema
Productions/CATALOGO` (copia ahí el contenido de `PROGRAMA\CATALOGO` o elige otra en Ajustes).

Cómo se crea: GitHub Actions lo compila y lo prueba solo en cada cambio que se sube a
https://github.com/alejandropiedrasanta1-ui/catalogo-cinema (pestaña Actions › artefacto «instalador-mac»).
También en una Mac: Terminal › `bash` + arrastrar `empaquetar/CREAR APP MAC.command` › Enter.
Ventana del instalador: `empaquetar/mac/instalador_mac.swift`; fondo del .dmg: `python empaquetar/mac/crear_fondo_dmg.py`.

## Probar

```
python catalogo_cinema.py --verificar          # arma la ventana sin mostrarla
python catalogo_cinema.py --captura cap.png    # abre, espera las miniaturas y guarda una captura
```
