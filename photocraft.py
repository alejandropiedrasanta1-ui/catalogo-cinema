"""PhotoCraft (ArtCraft) en segundo plano: «photocraft-cli serve» abre los PSD, aplica los cambios, recorta
cada página (mesa de trabajo) y la dibuja o la guarda.

- Un PSD por proceso: PhotoCraft numera las capas por proceso; abriendo cada PSD en un proceso nuevo los
  números son siempre los mismos (así las ediciones guardadas por número de capa siguen valiendo).
- En «serve» solo se puede escribir en rutas.TRABAJO; los archivos se mueven después a su destino.
- Se usa desde un solo hilo (el Trabajador), así que no necesita candados."""
import base64
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import rutas

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ErrorPhotoCraft(RuntimeError):
    pass


def buscar_photocraft():
    candidatos = []
    if rutas.ES_WINDOWS:
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            if base:
                candidatos += [os.path.join(base, "ArtCraft", "PhotoCraft", "photocraft-cli.exe"),
                               os.path.join(base, "PhotoCraft", "photocraft-cli.exe")]
    elif rutas.ES_MAC:
        for app in ("/Applications/PhotoCraft.app", os.path.expanduser("~/Applications/PhotoCraft.app"),
                    "/Applications/ArtCraft/PhotoCraft.app"):
            candidatos += [os.path.join(app, "Contents", "MacOS", "photocraft-cli"),
                           os.path.join(app, "Contents", "Resources", "photocraft-cli")]
    en_path = shutil.which("photocraft-cli")
    if en_path:
        candidatos.append(en_path)
    return next((c for c in candidatos if os.path.isfile(c)), None)


class Sesion:
    ESPERA = 90          # s por pedido normal
    ESPERA_LARGA = 900   # abrir o guardar PSD enormes
    LADO_MAX = 2048      # lo más grande que pinta «doc.render»

    def __init__(self):
        self.proc = None
        self.exe = ""
        self.lectura = []
        self.doc = None
        self.n = 0

    def configurar(self, exe, carpetas_lectura):
        lectura = sorted({str(Path(c).resolve()) for c in carpetas_lectura if c and os.path.isdir(c)})
        if exe != self.exe or lectura != self.lectura:
            self.cerrar()
        self.exe, self.lectura = exe, lectura

    def ejecutable(self):
        exe = self.exe if self.exe and os.path.isfile(self.exe) else buscar_photocraft()
        if not exe:
            raise ErrorPhotoCraft("No se encontró PhotoCraft (photocraft-cli).\n"
                                  "Instálalo o indica dónde está en Ajustes.")
        return exe

    # ---- proceso ----
    def apagar(self):
        """Cierra PhotoCraft para siempre (al salir del programa): ya no se vuelve a abrir."""
        self.apagada = True
        self.cerrar()

    def _iniciar(self):
        if getattr(self, "apagada", False):
            raise ErrorPhotoCraft("El programa se está cerrando.")
        if self.proc and self.proc.poll() is None:
            return
        rutas.preparar_carpetas()
        args = [self.ejecutable(), "serve", "--automation-write-root", str(rutas.TRABAJO.resolve())]
        for c in self.lectura + [str(rutas.DATOS.resolve())]:
            args += ["--automation-read-root", c]
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     errors="replace", creationflags=SIN_VENTANA)

    def _pedir(self, metodo, params, espera=None):
        proc = self.proc
        if not proc or proc.poll() is not None:
            raise ErrorPhotoCraft("PhotoCraft no está abierto.")
        self.n += 1
        reloj = threading.Timer(espera or self.ESPERA, self.cerrar)   # si se cuelga, se cierra
        reloj.start()
        try:
            proc.stdin.write(json.dumps({"id": self.n, "method": metodo, "params": params},
                                        ensure_ascii=False) + "\n")
            proc.stdin.flush()
            while True:
                linea = proc.stdout.readline()
                if not linea:
                    raise ErrorPhotoCraft("PhotoCraft se cerró (¿poca memoria libre o el archivo es muy grande?).")
                try:
                    r = json.loads(linea)
                except ValueError:
                    continue
                if r.get("id") == self.n:
                    break
        except OSError as e:
            raise ErrorPhotoCraft(f"PhotoCraft no responde: {e}")
        finally:
            reloj.cancel()
        if not r.get("ok"):
            raise ErrorPhotoCraft(f"PhotoCraft: {r.get('error')}")
        return r.get("result") or {}

    @staticmethod
    def cmd(comando, params=None):
        return "engine.execute", {"command": comando, "params": params or {}}

    def lote(self, pasos):
        if not pasos:
            return []
        r = self._pedir("batch", {"steps": [{"method": m, "params": p} for m, p in pasos]})
        resultados = r.get("results") or []
        for (m, p), res in zip(pasos, resultados):
            if not res.get("ok"):
                que = p.get("command", m) if isinstance(p, dict) else m
                raise ErrorPhotoCraft(f"PhotoCraft ({que}): {res.get('error')}")
        if len(resultados) != len(pasos):
            raise ErrorPhotoCraft("PhotoCraft: el lote quedó incompleto.")
        return [res.get("result") or {} for res in resultados]

    # ---- documento ----
    def abrir(self, psd):
        """Abre el PSD (si no es el que ya está abierto) y devuelve su árbol de capas."""
        psd = str(Path(psd).resolve())
        st = os.stat(psd)
        clave = (psd, st.st_mtime, st.st_size)
        if self.doc and self.doc["clave"] == clave and self.proc and self.proc.poll() is None:
            return self.doc["info"]
        self.cerrar()
        self._iniciar()
        self._pedir("doc.open", {"path": psd}, self.ESPERA_LARGA)
        info = self._pedir("doc.inspect", {})
        orig = self._pedir(*self.cmd("history.newSnapshot", {"name": "original"}))["snapshot"]
        self.doc = dict(clave=clave, info=info, orig=orig, editado=orig, firma="original")
        return info

    def preparar(self, pasos, firma):
        """Deja la instantánea «editado» = original + los cambios (solo se rehace si cambiaron)."""
        d = self.doc
        if d["firma"] == firma:
            return
        if d["editado"] != d["orig"]:
            try:
                self._pedir(*self.cmd("history.deleteSnapshot", {"snapshot": d["editado"]}))
            except ErrorPhotoCraft:
                pass
        d["editado"], d["firma"] = d["orig"], None
        self.lote([self.cmd("history.selectSnapshot", {"snapshot": d["orig"]}), *pasos])
        if pasos:
            d["editado"] = self._pedir(*self.cmd("history.newSnapshot", {"name": "editado"}))["snapshot"]
        d["firma"] = firma

    def pagina(self, rect, visibles=None):
        """Vuelve a lo editado y recorta a la página (rect = x, y, ancho, alto). Sin rect: el documento entero.
        visibles: {id de capa: bool} para las páginas hechas con grupos (se muestra solo el de esa página)."""
        d = self.doc
        pasos = [self.cmd("history.selectSnapshot", {"snapshot": d["editado"]})]
        for lid, si in (visibles or {}).items():
            pasos.append(self.cmd("layer.setProps", {"layer": int(lid), "visible": bool(si)}))
        if rect:
            x, y, w, h = (int(v) for v in rect)
            if (x, y, w, h) != (0, 0, d["info"]["width"], d["info"]["height"]):
                pasos.append(self.cmd("image.crop", {"x": x, "y": y, "width": w, "height": h}))
        self.lote(pasos)

    # (No hay «escalar»: el «Tamaño de imagen» de PhotoCraft deformaba varios diseños al re-dibujarlos.
    #  Para ampliar se usa ampliar.py, con IA, sobre la página ya dibujada a su tamaño original.)

    def dibujar(self, lado):
        """La imagen actual como PNG (bytes), con su lado mayor = lado px (máx. 2048).
        PhotoCraft no entrega PNG de más de 5 MB por esta vía (fotos grandes): se pide un poco más chica."""
        lado = int(max(256, min(lado, self.LADO_MAX)))
        while True:
            try:
                return base64.b64decode(self._pedir("doc.render", {"maxSide": lado})["base64"])
            except ErrorPhotoCraft as e:
                if "exceeds" not in str(e) or lado <= 800:
                    raise
                lado = int(lado * 0.8)

    def vivo(self):
        return bool(self.proc and self.proc.poll() is None)

    def con_reintento(self, psd, pasos, firma, trabajo):
        """Corre trabajo(); si PhotoCraft se cerró a medias (pasa muy de vez en cuando), lo vuelve a abrir
        con los mismos cambios y reintenta una vez."""
        try:
            return trabajo()
        except ErrorPhotoCraft:
            if self.vivo():
                raise   # fue un error del comando, no un cierre: reintentar no ayuda
            self.cerrar()
            time.sleep(2)   # deja que Windows libere la memoria del PhotoCraft que se cerró
            self.abrir(psd)
            self.preparar(pasos, firma)
            return trabajo()

    def guardar(self, destino, calidad=92):
        """Guarda la imagen actual (jpg, png o psd según la extensión) y la mueve a destino."""
        destino = Path(destino)
        tmp = rutas.TRABAJO / f"guardando_{os.getpid()}_{self.n}{destino.suffix.lower()}"
        params = {"path": str(tmp.resolve()), "metadata": "none"}
        if destino.suffix.lower() in (".jpg", ".jpeg", ".webp"):
            params["quality"] = int(calidad)
        self._pedir("doc.save", params, self.ESPERA_LARGA)
        if not tmp.exists():
            raise ErrorPhotoCraft("PhotoCraft terminó pero no se creó el archivo.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(destino))
        return destino

    def cerrar(self):
        proc, self.proc, self.doc = self.proc, None, None
        if proc and proc.poll() is None:
            try:
                proc.stdin.close()
            except OSError:
                pass
            try:
                proc.kill()
            except OSError:
                pass
