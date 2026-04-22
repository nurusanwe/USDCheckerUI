"""Generate the placeholder USDCheckerUI.ico.

Stdlib-only. Deterministic — byte-identical output across runs and across
Python 3.12 patch versions. The output is hash-pinned by
`tests/test_ico_placeholder.py` so any drift in the layout below is caught
by CI.

================================================================
ICO layout (no PNG embedding; classic BMP-in-ICO; bottom-up 32-bpp BGRA)
================================================================

Header layout, byte-by-byte (offsets assume one image):

  ICONDIR (6 B, at offset 0)
    uint16 reserved    = 0
    uint16 type        = 1                (ICO; 2 = CUR)
    uint16 count       = 1

  ICONDIRENTRY (16 B, at offset 6)
    uint8  width       = SIZE (0 means 256; we use 48 literally)
    uint8  height      = SIZE
    uint8  color_count = 0                (0 when bit_count >= 8)
    uint8  reserved    = 0
    uint16 planes      = 1
    uint16 bit_count   = 32               (BGRA)
    uint32 bytes_in_res = len(BITMAPINFOHEADER + XOR + AND)
    uint32 image_offset = 22              (6 + 16)

  BITMAPINFOHEADER (40 B, at offset 22)
    uint32 biSize          = 40
    int32  biWidth         = SIZE
    int32  biHeight        = 2 * SIZE     (XOR plane + AND plane — the
                                           single ICO quirk to remember)
    uint16 biPlanes        = 1
    uint16 biBitCount      = 32
    uint32 biCompression   = 0            (BI_RGB)
    uint32 biSizeImage     = len(XOR) + len(AND)
    int32  biXPelsPerMeter = 0
    int32  biYPelsPerMeter = 0
    uint32 biClrUsed       = 0
    uint32 biClrImportant  = 0

  XOR plane (at offset 62)
    SIZE rows, SIZE pixels/row, 4 B/pixel (BGRA), BOTTOM-UP row order
    (last row of the image first). At 32-bpp, row size (SIZE*4) is
    always a multiple of 4, so no row padding is needed.

  AND mask (immediately after XOR)
    SIZE rows, 1 bpp, row size ceil(SIZE/8) padded up to a multiple
    of 4 bytes. All zeros (fully opaque; transparency-by-zero).

For SIZE = 48:
    XOR bytes  = 48 * 48 * 4 = 9216
    AND stride = align4(ceil(48/8)) = align4(6) = 8
    AND bytes  = 48 * 8 = 384
    Total file = 6 + 16 + 40 + 9216 + 384 = 9662 B.

Color:
    BGRA = (180, 100, 30, 255). BMP DIBs store pixels as BGRA, not RGBA;
    the tuple name is a reminder — do NOT reorder.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

SIZE = 48
BGRA = (180, 100, 30, 255)  # Eclair-ish blue; stored BGRA because BMP is BGRA.


def _build_ico_bytes() -> bytes:
    width = SIZE
    height = SIZE

    # XOR plane: bottom-up rows of BGRA pixels.
    row = bytes(BGRA) * width
    xor_plane = row * height  # len = width * height * 4

    # AND mask: 1-bpp, row stride padded to multiple of 4 bytes.
    raw_row_bytes = (width + 7) // 8
    and_stride = (raw_row_bytes + 3) & ~3
    and_plane = b"\x00" * (and_stride * height)

    bitmap_info_header = struct.pack(
        "<IiiHHIIiiII",
        40,                           # biSize
        width,                        # biWidth
        2 * height,                   # biHeight (XOR + AND planes)
        1,                            # biPlanes
        32,                           # biBitCount
        0,                            # biCompression (BI_RGB)
        len(xor_plane) + len(and_plane),  # biSizeImage
        0,                            # biXPelsPerMeter
        0,                            # biYPelsPerMeter
        0,                            # biClrUsed
        0,                            # biClrImportant
    )

    image_blob = bitmap_info_header + xor_plane + and_plane

    icondir = struct.pack(
        "<HHH",
        0,  # reserved
        1,  # type = ICO
        1,  # count
    )

    icondirentry = struct.pack(
        "<BBBBHHII",
        width,               # width
        height,              # height
        0,                   # color_count (0 means >= 256 colors)
        0,                   # reserved
        1,                   # planes
        32,                  # bit_count
        len(image_blob),     # bytes_in_res
        6 + 16,              # image_offset (after ICONDIR + one ICONDIRENTRY)
    )

    return icondir + icondirentry + image_blob


def generate(output_dir: Path) -> Path:
    """Write USDCheckerUI.ico into output_dir. Returns the written path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "USDCheckerUI.ico"
    target.write_bytes(_build_ico_bytes())
    return target


def main() -> int:
    here = Path(__file__).resolve().parent
    target = generate(here)
    data = target.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f"Wrote {target} ({len(data)} bytes)")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
