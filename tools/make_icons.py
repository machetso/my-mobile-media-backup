#!/usr/bin/env python3
"""Build the app icons from assets/icon.svg (needs only PySide6).

    .venv/bin/python tools/make_icons.py

Writes:
    assets/icon.png                     512 px, transparent background (window icon)
    assets/icon.ico                     Windows icon, 16-256 px (program file, window)
    assets/hicolor/<N>x<N>/apps/my-smartphone-media-backup.png   Linux icon theme sizes
    android/app/src/main/res/mipmap-*/ic_launcher.png            phone app icon (old launchers)
    android/app/src/main/res/mipmap-*/ic_launcher_foreground.png adaptive icon layer (Android 8+):
        the drawing as big as the launcher's round shape allows, transparent background
        (without it the Pixel launcher shrinks the icon into a white circle)
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "icon.svg"
NAME = "my-smartphone-media-backup"
LINUX_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ANDROID_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# adaptive icon: 108 dp layer, the launcher shows at most the middle 72 dp (a circle on Pixel phones)
ADAPTIVE_SIZES = {dpi: n * 108 // 48 for dpi, n in ANDROID_SIZES.items()}
VISIBLE = 72 / 108
ADAPTIVE_XML = """<?xml version="1.0" encoding="utf-8"?>
<!-- built by tools/make_icons.py -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@android:color/transparent"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
"""


def render_master(n=1024) -> QImage:
    r = QSvgRenderer(str(SRC))
    if not r.isValid():
        sys.exit(f"Cannot read {SRC}")
    img = QImage(n, n, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    r.render(p, QRectF(0, 0, n, n))
    p.end()
    return img


def content_box(img: QImage) -> QRectF:
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(img.width()):
            if (img.pixel(x, y) >> 24) > 8:
                xs.append(x)
                ys.append(y)
    return QRectF(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def adaptive_foreground(master: QImage, n=1024) -> QImage:
    """The drawing as big as possible inside the visible circle of an adaptive icon layer."""
    small = scaled(master, 256)
    box = content_box(small)
    k = master.width() / 256
    box = QRectF(box.x() * k, box.y() * k, box.width() * k, box.height() * k)
    pts = [(x, y) for y in range(small.height()) for x in range(small.width()) if (small.pixel(x, y) >> 24) > 8]
    radius = n * VISIBLE / 2 - n * 0.004          # a hair inside, so no edge pixel is cut off
    cx0, cy0 = (box.x() + box.width() / 2) / k, (box.y() + box.height() / 2) / k
    far = max(((x + 0.5 - cx0) ** 2 + (y + 0.5 - cy0) ** 2) ** 0.5 for x, y in pts) * k   # in master pixels
    scale = radius / far
    out = QImage(n, n, QImage.Format_ARGB32)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    w, h = box.width() * scale, box.height() * scale
    p.drawImage(QRectF((n - w) / 2, (n - h) / 2, w, h), master, box)
    p.end()
    return out


def scaled(img: QImage, n: int) -> QImage:
    # Several halving steps give cleaner small icons than one big jump.
    cur = img
    while cur.width() > 2 * n:
        cur = cur.scaled(cur.width() // 2, cur.height() // 2, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return cur.scaled(n, n, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    b = QBuffer(ba)
    b.open(QIODevice.WriteOnly)
    img.save(b, "PNG")
    return bytes(ba)


def write_ico(path: Path, images):
    """ICO with PNG-compressed entries (supported since Windows Vista)."""
    blobs = [png_bytes(im) for im in images]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for im, data in zip(images, blobs):
        s = im.width()
        out += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(out + b"".join(blobs))


def main():
    QGuiApplication(sys.argv[:1])
    master = render_master()
    assets = ROOT / "assets"
    scaled(master, 512).save(str(assets / "icon.png"))
    for n in LINUX_SIZES:
        d = assets / "hicolor" / f"{n}x{n}" / "apps"
        d.mkdir(parents=True, exist_ok=True)
        scaled(master, n).save(str(d / f"{NAME}.png"))
    write_ico(assets / "icon.ico", [scaled(master, n) for n in ICO_SIZES])
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    for dpi, n in ANDROID_SIZES.items():
        scaled(master, n).save(str(res / f"mipmap-{dpi}" / "ic_launcher.png"))
    fg = adaptive_foreground(master)
    for dpi, n in ADAPTIVE_SIZES.items():
        scaled(fg, n).save(str(res / f"mipmap-{dpi}" / "ic_launcher_foreground.png"))
    d = res / "mipmap-anydpi-v26"
    d.mkdir(exist_ok=True)
    (d / "ic_launcher.xml").write_text(ADAPTIVE_XML, encoding="utf-8")
    print("written: assets/icon.png, assets/icon.ico, assets/hicolor/*, android mipmap-*/ic_launcher*.png + "
          "mipmap-anydpi-v26/ic_launcher.xml")


if __name__ == "__main__":
    main()
