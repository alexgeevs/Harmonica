#!/usr/bin/env python3
"""Generate Harmonica's PWA / iOS home-screen icons with no image libraries.

iOS Safari ignores SVG for `apple-touch-icon`, so we need real PNGs. Rather than
add a build dependency, this emits the PNGs directly using zlib + the PNG chunk
format. Run from the web/ dir:  python scripts/make_icons.py

Design: full-bleed deep-green field (iOS masks it to a squircle, so we do NOT
pre-round the corners) with a centred cluster of equaliser "reeds" in the teal
accent plus one gold reed echoing the rating stars.
"""
import struct
import zlib
from pathlib import Path

# Palette (matches web/src/styles.css and the sidebar).
BG = (0x20, 0x30, 0x2F)        # deep green sidebar
TEAL = (0x2C, 0x84, 0x73)      # accent-soft
TEAL_DK = (0x20, 0x6A, 0x5D)   # accent
GOLD = (0xF1, 0xC8, 0x4B)      # rating gold

# Reed heights as fractions of the inner band, left→right. The tallest is gold.
REEDS = [
    (0.46, TEAL),
    (0.70, TEAL_DK),
    (0.58, TEAL),
    (0.88, GOLD),
    (0.64, TEAL_DK),
]

OUT = Path(__file__).resolve().parent.parent / "public"


def rounded_rect_mask(w, h, x0, y0, x1, y1, r):
    """Yield (x, y) test via a closure; here we just precompute per-pixel."""
    def inside(x, y):
        if not (x0 <= x < x1 and y0 <= y < y1):
            return False
        # round only the corners of the reed
        cx = None
        cy = None
        if x < x0 + r:
            cx = x0 + r
        elif x >= x1 - r:
            cx = x1 - r - 1
        if y < y0 + r:
            cy = y0 + r
        elif y >= y1 - r:
            cy = y1 - r - 1
        if cx is not None and cy is not None:
            return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
        return True
    return inside


def render(size):
    px = bytearray(BG * (size * size))

    def put(x, y, rgb):
        i = (y * size + x) * 3
        px[i:i + 3] = bytes(rgb)

    # Layout the reed cluster in the centre.
    n = len(REEDS)
    band_h = int(size * 0.62)
    band_top = (size - band_h) // 2
    band_bot = band_top + band_h
    gap = size * 0.045
    total_gap = gap * (n + 1)
    reed_w = (size - total_gap) / n
    radius = max(2, int(reed_w * 0.30))

    x = gap
    for frac, color in REEDS:
        x0 = int(round(x))
        x1 = int(round(x + reed_w))
        rh = int(band_h * frac)
        y1 = band_bot
        y0 = band_bot - rh
        inside = rounded_rect_mask(size, size, x0, y0, x1, y1, radius)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if inside(xx, yy):
                    put(xx, yy, color)
        x += reed_w + gap

    # Pack into PNG scanlines (filter byte 0 per row).
    raw = bytearray()
    stride = size * 3
    for y in range(size):
        raw.append(0)
        raw.extend(px[y * stride:(y + 1) * stride])
    return png_bytes(size, size, bytes(raw))


def png_bytes(w, h, raw):
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit truecolor RGB
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {
        "apple-touch-icon.png": 180,   # iOS home screen
        "icon-192.png": 192,           # manifest (Android/Chrome)
        "icon-512.png": 512,           # manifest install / splash
        "favicon-32.png": 32,          # browser tab
    }
    for name, size in targets.items():
        (OUT / name).write_bytes(render(size))
        print(f"wrote public/{name} ({size}x{size})")


if __name__ == "__main__":
    main()
