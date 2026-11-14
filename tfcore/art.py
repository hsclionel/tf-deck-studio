"""Card artwork from `USRDIR/card/cardh_j.cip`.

CIP: u32 magic, u32 file size, 8 zero bytes, u32 header size, u32 first card, u32 last card,
u32 table offset (0x30), u32 sectors per entry, 12 zero bytes, then (u32, u32 0) per card number.
A table value is the entry's sector; with the top bit set it is a byte offset to a list of
(sector, 0) pairs, one per artwork, whose last sector carries the top bit.

cardh entries are GIM images: a 128x64 DXT1 atlas holding the 80x80 artwork (its top 80x60 on
the left; its bottom 80x20 strip split into 48x20 at (80,0) and 32x20 at (80,20)).
PSP DXT1 blocks store the 32-bit index word before the two RGB565 colours.
(cardm is a 64x64 whole-card thumbnail; cardj, likely full resolution, is not decoded.)
"""
import struct

import numpy as np
from PIL import Image

FLAG = 0x80000000


def cip_index(head):
    """Card number → list of entry sectors (one per artwork)."""
    _, _, _, _, _, first, last, toff, _ = struct.unpack_from('<4sIIIIIIII', head, 0)
    table = {}
    for i in range(last - first + 1):
        v = struct.unpack_from('<I', head, toff + i * 8)[0]
        if not v & FLAG:
            table[first + i] = [v]
            continue
        arts, off = [], v & ~FLAG
        while True:
            s = struct.unpack_from('<I', head, off)[0]
            arts.append(s & ~FLAG)
            if s & FLAG:
                break
            off += 8
        table[first + i] = arts
    return table


def _rgb565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)


def dxt1_psp(data, w, h):
    n = (w // 4) * (h // 4)
    blk = np.frombuffer(data[:n * 8], dtype='<u4').reshape(n, 2)
    idx, cols = blk[:, 0], blk[:, 1]
    c0, c1 = _rgb565(cols & 0xFFFF), _rgb565(cols >> 16)
    opaque = (cols & 0xFFFF) > (cols >> 16)
    c2 = np.where(opaque[:, None], (2 * c0 + c1) // 3, (c0 + c1) // 2)
    c3 = np.where(opaque[:, None], (c0 + 2 * c1) // 3, 0)
    palette = np.stack([c0, c1, c2, c3], 1)
    sel = (idx[:, None] >> (2 * np.arange(16))) & 3
    px = np.take_along_axis(palette, sel[:, :, None].repeat(3, 2), 1)
    img = px.reshape(h // 4, w // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, 3)
    return Image.fromarray(img.astype(np.uint8))


def gim(data):
    """Decode a GIM holding one DXT1 image."""
    if data[:11] != b'MIG.00.1PSP':
        raise ValueError('not a GIM')
    pos = 0x10
    while pos < len(data):
        bid, _, size, nxt, doff = struct.unpack_from('<HHIII', data, pos)
        if bid == 0x04:
            h = pos + doff
            fmt, order, w, hgt = struct.unpack_from('<HHHH', data, h + 4)
            if fmt != 8 or order != 0:
                raise ValueError(f'GIM format {fmt}/{order} not supported')
            return dxt1_psp(data[h + struct.unpack_from('<I', data, h + 0x1C)[0]:], w, hgt)
        pos += nxt if bid in (0x02, 0x03) else size
    raise ValueError('GIM without image block')


def artwork(atlas):
    """80x80 artwork from a cardh atlas; the last column/row is padding, so 79x79."""
    out = Image.new('RGB', (80, 80))
    out.paste(atlas.crop((0, 0, 80, 60)), (0, 0))
    out.paste(atlas.crop((80, 0, 128, 20)), (0, 60))
    out.paste(atlas.crop((80, 20, 112, 40)), (48, 60))
    return out.crop((0, 0, 79, 79))


def iter_artworks(cardh):
    """Yield (card number, artwork index, PIL image) for every decodable entry."""
    for num, sectors in cip_index(cardh).items():
        for k, s in enumerate(sectors):
            # An entry's GIM runs past its 2-sector slot; pad the last one in the file.
            raw = cardh[s * 2048:(s + 3) * 2048].ljust(3 * 2048, bytes(1))
            if raw[:3] == b'MIG':
                yield num, k, artwork(gim(raw))
