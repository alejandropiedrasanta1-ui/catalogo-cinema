"""Rehace recursos/icono.ico: 64-256 px desde icono.png; 16-48 px desde una versión simplificada (una sola hoja,
foto grande y dos barras) para que en el escritorio y la barra de tareas se vea nítido, no borroso.
python crear_ico.py"""
import subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageFilter

RAIZ = Path(__file__).resolve().parents[2]
REC = RAIZ / "recursos"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHICO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024"><defs>
<linearGradient id="f" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff6b57"/><stop offset=".45" stop-color="#e5252a"/><stop offset="1" stop-color="#8e1730"/></linearGradient>
<linearGradient id="o" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff3c4"/><stop offset=".5" stop-color="#e8c06a"/><stop offset="1" stop-color="#b07c2e"/></linearGradient></defs>
<rect x="40" y="40" width="944" height="944" rx="210" fill="url(#f)"/>
<g transform="rotate(-8 512 540)"><rect x="300" y="200" width="424" height="640" rx="46" fill="#fbe3dc" opacity=".9"/></g>
<rect x="270" y="190" width="484" height="660" rx="50" fill="#ffffff"/>
<rect x="320" y="240" width="384" height="320" rx="26" fill="url(#o)"/>
<circle cx="626" cy="320" r="38" fill="#fff8e1"/>
<path d="M320 500 L440 390 L530 470 L590 425 L704 515 V534 Q704 560 678 560 H346 Q320 560 320 534Z" fill="#8e1730"/>
<rect x="320" y="610" width="300" height="56" rx="28" fill="#2a0a12"/>
<rect x="320" y="710" width="190" height="60" rx="30" fill="#e5252a"/></svg>"""


def render_svg(svg, lado=1024):
    d = Path(tempfile.mkdtemp())
    h, png = d / "i.html", d / "i.png"
    h.write_text(f"<html><body style='margin:0;background:transparent'>{svg}</body></html>", encoding="utf-8")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={d / 'p'}",
                    "--default-background-color=00000000", f"--window-size={lado},{lado}", f"--screenshot={png}", h.as_uri()],
                   capture_output=True, timeout=120)
    import time
    for _ in range(40):                       # Edge a veces escribe la captura un poco después de salir
        if png.exists() and png.stat().st_size:
            break
        time.sleep(.5)
    return Image.open(png).convert("RGBA")


def main():
    grande = Image.open(REC / "icono.png").convert("RGBA")
    chico = render_svg(CHICO)
    imgs = []
    for s in (256, 128, 64, 48, 32, 24, 16):
        src = grande if s >= 64 else chico
        im = src.resize((s, s), Image.LANCZOS)
        if s <= 48:
            im = im.filter(ImageFilter.UnsharpMask(radius=.6, percent=60, threshold=0))
        imgs.append(im)
    imgs[0].save(REC / "icono.ico", format="ICO", sizes=[i.size for i in imgs], append_images=imgs[1:])
    print("ok", [i.size for i in imgs])


if __name__ == "__main__":
    main()
