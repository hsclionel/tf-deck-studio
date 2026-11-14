"""TF6 player deck slots in a decrypted DATA0 (layout: research doc / ygotfToolkit FORMATS.md §10).

  python -I tfdeck.py list <plain>
  python -I tfdeck.py write <plain> <deck.json> <out plain>

deck.json: {"slot": 3, "name": "...", "main": [[num, copies], ...], "extra": [...], "side": [...]}
A new slot gets the current local time and a random 20-bit tag; an existing slot keeps both.
"""
import datetime, json, random, struct, sys

DECKS, SLOT, NSLOTS = 0x20, 436, 200
MAX_MAIN, MAX_EXTRA, MAX_SIDE = 60, 15, 15


def slot_off(i):
    assert 0 <= i < NSLOTS
    return DECKS + i * SLOT


def read_slot(b, i):
    o = slot_off(i)
    in_use, = struct.unpack_from('<I', b, o)
    name = b[o + 4:o + 0x84].decode('utf-16le').split('\0')[0]
    tag, mc, unk, ec = struct.unpack_from('<4I', b, o + 0x90)
    sc, = struct.unpack_from('<I', b, o + 0x154)
    return dict(in_use=in_use, name=name, ts=struct.unpack_from('<6H', b, o + 0x84), tag=tag, unk98=unk,
                main=list(struct.unpack_from(f'<{mc}H', b, o + 0xA0)),
                extra=list(struct.unpack_from(f'<{ec}H', b, o + 0x136)),
                side=list(struct.unpack_from(f'<{sc}H', b, o + 0x158)))


def expand(pairs):
    return [num for num, n in pairs for _ in range(n)]


def write_slot(b, i, name, main, extra, side):
    assert 40 <= len(main) <= MAX_MAIN and len(extra) <= MAX_EXTRA and len(side) <= MAX_SIDE
    o = slot_off(i)
    old = read_slot(b, i)
    if old['in_use']:
        ts, tag = old['ts'], old['tag']
    else:
        now = datetime.datetime.now()
        ts = (now.year, now.month, now.day, now.hour, now.minute, now.second)
        tags = {read_slot(b, s)['tag'] for s in range(NSLOTS)}
        tag = random.choice([t for t in random.sample(range(1, 1 << 20), 16) if t not in tags])
    enc = name.encode('utf-16le') + b'\0\0'
    assert len(enc) <= 0x80
    struct.pack_into('<I', b, o, 1)
    b[o + 4:o + 0x84] = enc + bytes(0x80 - len(enc))
    struct.pack_into('<6H', b, o + 0x84, *ts)
    struct.pack_into('<4I', b, o + 0x90, tag, len(main), old['unk98'], len(extra))
    b[o + 0xA0:o + 0x136] = struct.pack(f'<{len(main)}H', *main) + bytes(0x96 - 2 * len(main))
    b[o + 0x136:o + 0x154] = struct.pack(f'<{len(extra)}H', *extra) + bytes(0x1E - 2 * len(extra))
    struct.pack_into('<I', b, o + 0x154, len(side))
    b[o + 0x158:o + 0x176] = struct.pack(f'<{len(side)}H', *side) + bytes(0x1E - 2 * len(side))
    # +0x176..+0x1B4 is unknown and left as it was.


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    b = bytearray(open(argv[2], 'rb').read())
    if argv[1] == 'list':
        for i in range(NSLOTS):
            s = read_slot(b, i)
            if s['in_use']:
                print(f"{i:3} {s['name']!r} main={len(s['main'])} extra={len(s['extra'])} side={len(s['side'])} "
                      f"tag={s['tag']:#x} ts={s['ts']}")
    elif argv[1] == 'write':
        d = json.load(open(argv[3], encoding='utf-8'))
        write_slot(b, d['slot'], d['name'], expand(d['main']), expand(d.get('extra', [])), expand(d.get('side', [])))
        open(argv[4], 'wb').write(b)


if __name__ == '__main__':
    main(sys.argv)
