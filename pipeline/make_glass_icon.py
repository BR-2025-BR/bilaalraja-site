#!/usr/bin/env python3
"""Render a Liquid-Glass-styled variant of the scatter icon.

    python3 pipeline/make_glass_icon.py            writes docs/icon-glass-*.png
    python3 pipeline/make_glass_icon.py --apply    replaces the live icon set

A real Liquid Glass icon is a layered .icon bundle that iOS composites at
runtime, responding to light, dark and tinted appearances. A web app can only
supply a flat PNG, so this is a rendering of the material rather than the
material itself: it picks one lighting condition and bakes it in.

The scatter geometry is unchanged -- axes at x=85 (y 71-428) and y=425
(x 83-440), eight orange points at r=21, four grey at r=15 -- because the splash
animation and all 36 launch images are generated from those same coordinates.
Only the material changes.
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "docs"
S = 1024                      # render big, downsample at the end
K = S / 512                   # icon coordinates are in 512 space

ORANGE = (255, 153, 0)
GREY = (71, 71, 71)
AXIS = (120, 120, 124)

DOTS = [(150, 339, 15, GREY), (175, 378, 21, ORANGE), (195, 268, 21, ORANGE),
        (237, 300, 21, ORANGE), (262, 195, 15, GREY), (276, 351, 15, GREY),
        (299, 244, 21, ORANGE), (329, 150, 21, ORANGE), (352, 207, 15, GREY),
        (357, 300, 21, ORANGE), (385, 124, 21, ORANGE), (403, 244, 21, ORANGE)]


def linear_gradient(size, top, bottom):
    """Vertical ramp, the base of the glass slab."""
    y = np.linspace(0, 1, size)[:, None]
    img = np.zeros((size, size, 3))
    for c in range(3):
        img[:, :, c] = top[c] + (bottom[c] - top[c]) * y
    return Image.fromarray(img.astype(np.uint8))


def sphere(d, colour):
    """A dot with a specular highlight, so it reads as glass rather than paint."""
    n = d * 4                                   # supersample, then shrink
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    px = im.load()
    r = n / 2
    lx, ly, lz = -0.45, -0.55, 0.70             # light from upper-left
    for yy in range(n):
        for xx in range(n):
            nx, ny = (xx - r + .5) / r, (yy - r + .5) / r
            q = nx * nx + ny * ny
            if q > 1:
                continue
            nz = math.sqrt(1 - q)
            lam = max(0.0, -(nx * lx + ny * ly + nz * lz))
            spec = max(0.0, -(nx * lx + ny * ly + nz * lz)) ** 18
            # Shallow shading. The first attempt used 0.58 + 0.42*lam, which
            # dimmed #FF9900 to brown and cost the icon its legibility at the
            # ~60px it is actually viewed at. Glass reads from the highlight,
            # not from darkening the body.
            base = 0.86 + 0.14 * lam
            col = [min(255, int(c * base + 255 * spec * 0.95)) for c in colour]
            edge = min(1.0, (1 - math.sqrt(q)) * r * 0.9)   # antialias the rim
            px[xx, yy] = (col[0], col[1], col[2], int(255 * edge))
    return im.resize((d, d), Image.LANCZOS)


def build():
    # --- the slab: a dark glass panel, not flat black
    img = linear_gradient(S, (38, 39, 44), (13, 13, 16)).convert("RGBA")

    # --- a broad diagonal sheen across the panel
    sheen = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(sheen)
    d.polygon([(-S * .1, S * .42), (S * .62, -S * .1), (S * .95, S * .06),
               (S * .1, S * .78)], fill=64)
    sheen = sheen.filter(ImageFilter.GaussianBlur(S * 0.085))
    img = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), img, sheen)

    # --- specular rim along the top and left, the tell of the material
    rim = Image.new("L", (S, S), 0)
    r = ImageDraw.Draw(rim)
    pad = S * 0.035
    r.rounded_rectangle([pad, pad, S - pad, S - pad], radius=S * 0.22,
                        outline=150, width=int(S * 0.012))
    rim = rim.filter(ImageFilter.GaussianBlur(S * 0.010))
    fade = np.linspace(1.0, 0.0, S)[:, None] * np.linspace(1.0, 0.25, S)[None, :]
    rim = Image.fromarray((np.asarray(rim) * fade).astype(np.uint8))
    img = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), img, rim)

    # --- the chart, unchanged in geometry, lifted off the glass by a shadow
    art = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    a = ImageDraw.Draw(art)
    w = int(6 * K)
    a.line([(85 * K, 71 * K), (85 * K, 425 * K)], fill=AXIS, width=w)
    a.line([(83 * K, 425 * K), (440 * K, 425 * K)], fill=AXIS, width=w)
    for x, y, rad, col in DOTS:
        dd = int(rad * 2 * K)
        art.alpha_composite(sphere(dd, col), (int(x * K - dd / 2), int(y * K - dd / 2)))

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (0, int(S * .012)), art.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.018))
    img.alpha_composite(shadow)
    img.alpha_composite(art)
    return img.convert("RGB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="replace icon-512/192 and apple-touch-icon")
    args = ap.parse_args()

    full = build()
    preview = SITE / "icon-glass-512.png"
    full.resize((512, 512), Image.LANCZOS).save(preview, optimize=True)
    full.resize((180, 180), Image.LANCZOS).save(SITE / "icon-glass-180.png", optimize=True)
    print(f"  wrote {preview.name} and icon-glass-180.png")

    if args.apply:
        full.resize((512, 512), Image.LANCZOS).save(SITE / "icon-512.png", optimize=True)
        full.resize((192, 192), Image.LANCZOS).save(SITE / "icon-192.png", optimize=True)
        full.resize((180, 180), Image.LANCZOS).save(SITE / "apple-touch-icon.png", optimize=True)
        print("  applied to icon-512, icon-192 and apple-touch-icon")
        print("  NOTE: re-run make_splash_images.py -- the launch images embed the icon")
