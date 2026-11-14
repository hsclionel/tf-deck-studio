"""Card art from Tag Force `USRDIR/card/card{m,h,j}_j.cip`.

CIP layout (TF6, inferred 2026-10-27): u32 magic ("CPM\\x1a"/"CIP\\x1a"/"CPJ\\x1a"), u32 file size,
8 zero bytes, u32 header size, u32 first card number, u32 last card number, u32 0x30 (table offset),
u32 sectors per entry, 12 zero bytes; then one (u32 sector, u32 0) pair per card number.
Entries are GIM images (cardh, cardj) or bare DXT1 blocks (cardm). PSP DXT1 blocks store the
32-bit index word before the two RGB565 colours.

  python cardart.py <entry.bin> <out.png> [width height]
"""
import struct, sys

import numpy as np
from PIL import Image


FLAG = 0x80000000


def cip_index(head):
    """Card number → list of entry sectors (one per artwork; alt-art cards have several).
    A table value with the top bit set is a byte offset into the header where a list of
    (sector, 0) pairs starts; the top bit on a sector marks the last one in that list."""
    magic, size, _, _, hsize, first, last, toff, per = struct.unpack_from('<4sIIIIIIII', head, 0)
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
    return dict(magic=magic, first=first, last=last, per=per, header=hsize, table=table)


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
    palette = np.stack([c0, c1, c2, c3], 1)                       # (n, 4, 3)
    sel = (idx[:, None] >> (2 * np.arange(16))) & 3               # (n, 16)
    px = np.take_along_axis(palette, sel[:, :, None].repeat(3, 2), 1)  # (n, 16, 3)
    img = px.reshape(h // 4, w // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, 3)
    return Image.fromarray(img.astype(np.uint8))


def gim(data):
    """Decode a GIM holding one DXT1 image; returns a PIL image."""
    assert data[:11] == b'MIG.00.1PSP', data[:12]
    pos = 0x10
    while pos < len(data):
        bid, _, size, nxt, doff = struct.unpack_from('<HHIII', data, pos)
        if bid == 0x04:
            h = pos + doff
            fmt, order, w, hgt = struct.unpack_from('<HHHH', data, h + 4)
            pix = struct.unpack_from('<I', data, h + 0x1C)[0]
            assert fmt == 8 and order == 0, (fmt, order)
            return dxt1_psp(data[h + pix:], w, hgt)
        pos += nxt if bid in (0x02, 0x03) else size
    raise ValueError('no image block')


def artwork(atlas):
    """cardh atlases are 128x64: the artwork's top 80x60 on the left, its bottom 80x20 strip cut into
    48x20 (top right) and 32x20 (below that). The last column/row is padding, so 79x79 is returned."""
    out = Image.new('RGB', (80, 80))
    out.paste(atlas.crop((0, 0, 80, 60)), (0, 0))
    out.paste(atlas.crop((80, 0, 128, 20)), (0, 60))
    out.paste(atlas.crop((80, 20, 112, 40)), (48, 60))
    return out.crop((0, 0, 79, 79))


def build_cache(cardh_path, out_dir, scale=2):
    """Write <num>_<k>.webp (k = artwork index; >0 are alternate arts) for every card."""
    import os
    data = open(cardh_path, 'rb').read()
    ix = cip_index(data)
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for num, sectors in ix['table'].items():
        for k, s in enumerate(sectors):
            raw = data[s * 2048:(s + 3) * 2048].ljust(3 * 2048, bytes(1))
            if raw[:3] != b'MIG':
                continue
            try:
                img = artwork(gim(raw))
            except ValueError:
                print(f'skip {num}_{k}: truncated entry at sector {s}', file=sys.stderr)
                continue
            img.resize((79 * scale, 79 * scale), Image.LANCZOS).save(os.path.join(out_dir, f'{num}_{k}.webp'), quality=88)
            count += 1
    return count


if __name__ == '__main__':
    if sys.argv[1] == 'build':
        print(build_cache(sys.argv[2], sys.argv[3]), 'images')
    else:
        raw = open(sys.argv[1], 'rb').read()
        img = gim(raw) if raw[:3] == b'MIG' else dxt1_psp(raw, int(sys.argv[3]), int(sys.argv[4]))
        img.save(sys.argv[2])
        print(img.size)
