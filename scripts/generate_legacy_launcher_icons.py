#!/usr/bin/env python3
"""Generate pre-API-26 square launcher mipmaps from the approved marks.

Does not touch adaptive XML, monochrome, splash, or round mipmaps.
Each density/night variant is a rounded-rect silhouette: transparent
outer margin (12.5% of the tile), brand fill, and the first-party mark
centered at 72% of the inner box so proportions stay consistent.

Stdlib only (PNG decode/encode + zlib). Re-run:

  python3 scripts/generate_legacy_launcher_icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARK_LIGHT = (
    REPO_ROOT
    / "shared/src/commonMain/composeResources/drawable/kardano_mark_light.png"
)
MARK_DARK = (
    REPO_ROOT
    / "shared/src/commonMain/composeResources/drawable/kardano_mark_dark.png"
)
ANDROID_RES = REPO_ROOT / "androidApp/src/main/res"

# Brand fills from the Playground adaptive background.
LIGHT_FILL = (0xFA, 0xF9, 0xFF, 0xFF)
NIGHT_FILL = (0x0E, 0x0C, 0x13, 0xFF)

# mdpi..xxxhdpi legacy launcher tiles.
SIZES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

OUTER_PAD_RATIO = 0.125
MARK_RATIO = 0.72
CORNER_RATIO = 0.22


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos = 8
    width = height = bit = color = None
    raw = b""
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit, color, *_ = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            raw += chunk
        elif kind == b"IEND":
            break
    if width is None or height is None or bit != 8 or color != 6:
        raise ValueError(f"{path} must be 8-bit RGBA")
    payload = zlib.decompress(raw)
    bpp = 4
    stride = width * bpp
    out = bytearray()
    prev = bytearray(stride)
    i = 0
    for _ in range(height):
        filt = payload[i]
        i += 1
        row = bytearray(payload[i : i + stride])
        i += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                c = prev[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + _paeth(a, prev[x], c)) & 255
        elif filt != 0:
            raise ValueError(f"unsupported PNG filter {filt}")
        out.extend(row)
        prev = row
    return width, height, bytes(out)


def write_png_rgba(path: Path, width: int, height: int, pixels: bytes) -> None:
    if len(pixels) != width * height * 4:
        raise ValueError("pixel buffer size mismatch")
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def sample_bilinear(src_w: int, src_h: int, src: bytes, x: float, y: float) -> tuple[int, int, int, int]:
    if x < 0 or y < 0 or x > src_w - 1 or y > src_h - 1:
        return (0, 0, 0, 0)
    x0 = int(x)
    y0 = int(y)
    x1 = min(x0 + 1, src_w - 1)
    y1 = min(y0 + 1, src_h - 1)
    fx = x - x0
    fy = y - y0

    def pix(px: int, py: int) -> tuple[int, int, int, int]:
        i = (py * src_w + px) * 4
        return src[i], src[i + 1], src[i + 2], src[i + 3]

    c00 = pix(x0, y0)
    c10 = pix(x1, y0)
    c01 = pix(x0, y1)
    c11 = pix(x1, y1)
    out = []
    for ch in range(4):
        top = c00[ch] * (1 - fx) + c10[ch] * fx
        bot = c01[ch] * (1 - fx) + c11[ch] * fx
        out.append(int(top * (1 - fy) + bot * fy + 0.5))
    return out[0], out[1], out[2], out[3]


def inside_rounded_rect(x: int, y: int, left: int, top: int, right: int, bottom: int, radius: int) -> bool:
    if x < left or x >= right or y < top or y >= bottom:
        return False
    if radius <= 0:
        return True
    cx = x
    cy = y
    if left + radius <= cx < right - radius or top + radius <= cy < bottom - radius:
        return True
    corners = (
        (left + radius, top + radius),
        (right - radius - 1, top + radius),
        (left + radius, bottom - radius - 1),
        (right - radius - 1, bottom - radius - 1),
    )
    for ox, oy in corners:
        if (cx - ox) ** 2 + (cy - oy) ** 2 <= radius * radius:
            if (cx <= left + radius or cx >= right - radius - 1) and (
                cy <= top + radius or cy >= bottom - radius - 1
            ):
                return True
    # Interior of the four edge bands already returned True. Corner
    # pixels outside the quarter-circles stay False.
    in_corner_x = cx < left + radius or cx >= right - radius
    in_corner_y = cy < top + radius or cy >= bottom - radius
    if in_corner_x and in_corner_y:
        nearest = min(corners, key=lambda c: (cx - c[0]) ** 2 + (cy - c[1]) ** 2)
        return (cx - nearest[0]) ** 2 + (cy - nearest[1]) ** 2 <= radius * radius
    return True


def compose_tile(
    size: int,
    mark_w: int,
    mark_h: int,
    mark: bytes,
    fill: tuple[int, int, int, int],
) -> bytes:
    pad = max(int(round(size * OUTER_PAD_RATIO)), 6)
    inner = size - (2 * pad)
    radius = max(int(round(inner * CORNER_RATIO)), 4)
    mark_box = max(int(round(inner * MARK_RATIO)), 8)
    mark_origin = (size - mark_box) / 2.0
    out = bytearray(size * size * 4)
    left = pad
    top = pad
    right = size - pad
    bottom = size - pad
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            if not inside_rounded_rect(x, y, left, top, right, bottom, radius):
                out[i : i + 4] = b"\x00\x00\x00\x00"
                continue
            sx = (x + 0.5 - mark_origin) * (mark_w / mark_box) - 0.5
            sy = (y + 0.5 - mark_origin) * (mark_h / mark_box) - 0.5
            mr, mg, mb, ma = sample_bilinear(mark_w, mark_h, mark, sx, sy)
            if ma == 0:
                out[i : i + 4] = bytes(fill)
                continue
            inv = 255 - ma
            out[i] = (mr * ma + fill[0] * inv + 127) // 255
            out[i + 1] = (mg * ma + fill[1] * inv + 127) // 255
            out[i + 2] = (mb * ma + fill[2] * inv + 127) // 255
            out[i + 3] = 255
    return bytes(out)


def main() -> int:
    light_w, light_h, light = read_png_rgba(MARK_LIGHT)
    dark_w, dark_h, dark = read_png_rgba(MARK_DARK)
    variants = (
        ("", LIGHT_FILL, light_w, light_h, light),
        ("night-", NIGHT_FILL, dark_w, dark_h, dark),
    )
    written = 0
    for density, size in SIZES.items():
        for prefix, fill, mw, mh, mark in variants:
            dest = ANDROID_RES / f"mipmap-{prefix}{density}" / "ic_launcher.png"
            write_png_rgba(dest, size, size, compose_tile(size, mw, mh, mark, fill))
            written += 1
            print(f"wrote {dest.relative_to(REPO_ROOT)} ({size}x{size})")
    print(f"generated {written} legacy launcher tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
