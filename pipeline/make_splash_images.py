#!/usr/bin/env python3
"""Generate iOS launch images for the installed web app.

    python3 pipeline/make_splash_images.py

iOS shows an apple-touch-startup-image before a single byte of HTML is parsed,
which is earlier than any CSS splash can possibly be. Without one the launch
shows the manifest's background_color -- flat black here -- until the document
renders. With one, the icon is on screen from the first frame.

The icon is drawn at exactly the size and position the CSS splash puts it, so
the handoff from the native launch image to the animated one is invisible: the
static image is the animation's first frame held still.

iOS matches these by exact device dimensions, so each device and orientation
needs its own file and its own media query. A device with no match falls back to
background_color, which is the current behaviour -- so an unlisted device is no
worse off than before.
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "docs"
OUT = SITE / "splash"
BG = (0, 0, 0)

# device-width, device-height, device-pixel-ratio. CSS pixels, portrait.
DEVICES = [
    (320, 568, 2),   # SE 1st gen
    (375, 667, 2),   # 6, 7, 8, SE 2nd/3rd
    (414, 736, 3),   # 6+, 7+, 8+
    (375, 812, 3),   # X, XS, 11 Pro, 12/13 mini
    (414, 896, 2),   # XR, 11
    (414, 896, 3),   # XS Max, 11 Pro Max
    (390, 844, 3),   # 12, 13, 14, 16e
    (428, 926, 3),   # 12/13 Pro Max, 14 Plus
    (393, 852, 3),   # 14 Pro, 15, 15 Pro, 16
    (430, 932, 3),   # 14 Pro Max, 15 Plus/Pro Max, 16 Plus
    (402, 874, 3),   # 16 Pro
    (440, 956, 3),   # 16 Pro Max
    (744, 1133, 2),  # iPad mini 6
    (768, 1024, 2),  # iPad 9.7
    (810, 1080, 2),  # iPad 10.2
    (820, 1180, 2),  # iPad Air 10.9
    (834, 1194, 2),  # iPad Pro 11
    (1024, 1366, 2), # iPad Pro 12.9
]


def icon_px(css_w: int, dpr: int) -> int:
    """Match the CSS splash exactly: width: min(44vw, 184px)."""
    return int(round(min(css_w * 0.44, 184) * dpr))


def axes_art(size: int) -> Image.Image:
    """The axes alone, at the size and colour the CSS splash draws them.

    NOT the icon. The launch image has to be the animation's FIRST frame, and
    the animation opens with the axes drawn and no points -- the points land
    afterwards. Embedding the finished icon here produced the opposite: the
    complete chart on launch, then a blank splash, then the whole thing
    redrawing. Handing over mid-sequence makes the seam invisible.
    """
    from PIL import ImageDraw
    n = size * 4                                  # supersample for a clean edge
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = n / 512                                   # icon coordinates are 512-space
    w = max(1, int(round(6 * k)))
    d.line([(85 * k, 71 * k), (85 * k, 425 * k)], fill=(51, 51, 51, 255), width=w)
    d.line([(83 * k, 425 * k), (440 * k, 425 * k)], fill=(51, 51, 51, 255), width=w)
    return im.resize((size, size), Image.LANCZOS)


def build() -> list[tuple[str, int, int, int, str]]:
    OUT.mkdir(exist_ok=True)
    made = []
    for w, h, dpr in DEVICES:
        for orient, (cw, ch) in (("portrait", (w, h)), ("landscape", (h, w))):
            px_w, px_h = cw * dpr, ch * dpr
            # the icon is sized off the PORTRAIT width in both orientations, so it
            # stays the same physical size when the device is turned
            size = icon_px(min(w, h), dpr)
            canvas = Image.new("RGB", (px_w, px_h), BG)
            art = axes_art(size)
            canvas.paste(art, ((px_w - size) // 2, (px_h - size) // 2), art)
            name = f"{cw}x{ch}@{dpr}x-{orient}.png"
            # the art is three flat colours on black, so a palette costs nothing
            canvas.convert("P", palette=Image.ADAPTIVE, colors=64).save(
                OUT / name, optimize=True)
            made.append((name, cw, ch, dpr, orient))
    return made


def link_tags(made) -> str:
    out = []
    for name, cw, ch, dpr, orient in made:
        out.append(
            f'<link rel="apple-touch-startup-image" '
            f'media="(device-width: {cw}px) and (device-height: {ch}px) and '
            f'(-webkit-device-pixel-ratio: {dpr}) and (orientation: {orient})" '
            f'href="/splash/{name}">'
        )
    return "\n".join(out)


if __name__ == "__main__":
    made = build()
    total = sum((OUT / n).stat().st_size for n, *_ in made)
    print(f"  wrote {len(made)} launch images to {OUT}  ({total/1e3:,.0f} KB total, "
          f"mean {total/len(made)/1e3:.1f} KB)")
    (HERE / "splash_links.html").write_text(link_tags(made) + "\n")
    print(f"  wrote {HERE / 'splash_links.html'}")
