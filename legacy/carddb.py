"""Card table from a Tag Force cardinfo_jpn.ehp (TF6 `_J` layout).

  python -I carddb.py <cardinfo_jpn.ehp> <out.tsv>

Columns: card number (Konami id), row, passcode, kind, ATK, DEF, level, name.
"""
import json, re, struct, sys

ATTR = {1: 'LIGHT', 2: 'DARK', 3: 'WATER', 4: 'FIRE', 5: 'EARTH', 6: 'WIND', 7: 'DIVINE', 8: 'Spell', 9: 'Trap'}


def ehp_members(b):
    magic, _, tag, n = struct.unpack_from('<II4sI', b, 0)
    assert magic == 0x03504845 and tag == b'NOT ', (hex(magic), tag)
    out = {}
    for i in range(n):
        no, do = struct.unpack_from('<II', b, 16 + i * 8)
        name = b[no:b.index(b'\0', no)].decode()
        size = struct.unpack_from('<I', b, no + len(name) + 1)[0]
        out[name] = b[do:do + size]
    return out


def huffman_text(desc, huff, bitpos):
    """CARD_Desc: MSB-first bits walk CARD_Huff nodes (u16 child for bit 0, u16 for bit 1);
    a node whose child is 0 is a leaf with its UTF-16 char at +4, and the bit that reached it
    is read again from the root. U+0000 ends the text (port of ogy's huffman.ts)."""
    out, node = [], 0
    while True:
        bit = (desc[bitpos >> 3] >> (7 - (bitpos & 7))) & 1
        child = struct.unpack_from('<H', huff, node + bit * 2)[0]
        if child:
            node, bitpos = child, bitpos + 1
            continue
        ch = huff[node + 4:node + 6].decode('utf-16le')
        if ch == '\0':
            return ''.join(out)
        out.append(ch)
        node = 0


def load(path):
    m = ehp_members(open(path, 'rb').read())
    suffix = '_J' if 'CARD_Name_J.bin' in m else '_R'
    names, indx = m[f'CARD_Name{suffix}.bin'], m[f'CARD_Indx{suffix}.bin']
    desc, huff = m[f'CARD_Desc{suffix}.bin'], m[f'CARD_Huff{suffix}.bin']
    prop, pas = m['CARD_Prop.bin'], m['CARD_Pass.bin']
    rows = len(prop) // 8
    cards = []
    for r in range(rows):
        v, atk, dfn, f1, f2 = struct.unpack_from('<HBBHH', prop, r * 8)
        num = v & 0x3FFF
        if num == 0:
            continue
        no = struct.unpack_from('<I', indx, r * 8)[0]
        end = no
        while names[end:end + 2] != b'\0\0':
            end += 2
        name = re.sub(r'\$C\d', '', names[no:end].decode('utf-16le', 'replace'))
        attr = (f1 >> 6) & 0xF
        text = huffman_text(desc, huff, struct.unpack_from('<I', indx, r * 8 + 4)[0])
        cards.append(dict(num=num, row=r, pas=struct.unpack_from('<I', pas, r * 4)[0],
                          kind=ATTR.get(attr, f'?{attr}'), atk=atk * 40 + (20 if v & 0x8000 else 0),
                          dfn=dfn * 20, level=(f1 >> 10) & 0x3F, name=name, text=text))
    # `$mNNNN` in a text is the name of card NNNN.
    by_num = {c['num']: c['name'] for c in cards}
    for c in cards:
        c['text'] = re.sub(r'\$m(\d+)', lambda mm: by_num.get(int(mm.group(1)), mm.group(0)), c['text'])
    return cards


if __name__ == '__main__':
    cards = load(sys.argv[1])
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write('num\trow\tpasscode\tkind\tatk\tdef\tlevel\tname\n')
        for c in cards:
            f.write('{num}\t{row}\t{pas}\t{kind}\t{atk}\t{dfn}\t{level}\t{name}\n'.format(**c))
    texts = sys.argv[2].rsplit('.', 1)[0] + '_text.json'
    json.dump({c['num']: c['text'] for c in cards}, open(texts, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{len(cards)} cards -> {sys.argv[2]}, texts -> {texts}')
