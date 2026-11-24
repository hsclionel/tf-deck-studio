"""Typed view over a decrypted TF6 or TFSP DATA0 (layout: research doc / ygotfToolkit FORMATS.md §10,
verified in-game 2026-10-27 for names, new slots and card lists). TFSP uses the same 200 deck slots
at 0x20; only the plaintext size and the trunk offset differ (see games.Game).

Only deck slots are writable. The trunk (card collection) is read-only by design.
"""
import datetime, random, struct
from dataclasses import dataclass, field

PLAIN_SIZE = 0x47000
DECKS, SLOT_SIZE, NSLOTS = 0x20, 436, 200
TRUNK = 0x29418
MAIN_MIN, MAIN_MAX, SIDE_MAX, EXTRA_MAX = 40, 60, 15, 15
# Slot field offsets
IN_USE, NAME, NAME_LEN, STAMP, TAG, N_MAIN, UNK98, N_EXTRA = 0x0, 0x4, 0x80, 0x84, 0x90, 0x94, 0x98, 0x9C
MAIN, MAIN_CAP, EXTRA, N_SIDE, SIDE = 0xA0, 75, 0x136, 0x154, 0x158


@dataclass
class Deck:
    name: str
    main: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    side: list = field(default_factory=list)
    stamp: tuple = None      # (Y, M, D, h, m, s)
    tag: int = 0             # per-deck 20-bit value; any fresh random value works

    def counts(self):
        out = {}
        for n in self.main + self.extra + self.side:
            out[n] = out.get(n, 0) + 1
        return out


class TF6Save:
    def __init__(self, plain, game=None):
        size = game.plain_size if game else PLAIN_SIZE
        if len(plain) != size:
            raise ValueError(f'DATA0 must decrypt to {size:#x} bytes, got {len(plain):#x}')
        self.data = bytearray(plain)
        self.trunk_offset = game.trunk if game else TRUNK

    # ---- general
    @property
    def play_seconds(self):
        return struct.unpack_from('<I', self.data, 0xC)[0] / 30

    # ---- decks
    def _off(self, slot):
        if not 0 <= slot < NSLOTS:
            raise IndexError(slot)
        return DECKS + slot * SLOT_SIZE

    def in_use(self, slot):
        return struct.unpack_from('<I', self.data, self._off(slot))[0] == 1

    def deck(self, slot):
        o = self._off(slot)
        d = self.data
        tag, n_main, _, n_extra = struct.unpack_from('<4I', d, o + TAG)
        n_side = struct.unpack_from('<I', d, o + N_SIDE)[0]
        return Deck(name=d[o + NAME:o + NAME + NAME_LEN].decode('utf-16le').split('\0')[0],
                    main=list(struct.unpack_from(f'<{n_main}H', d, o + MAIN)),
                    extra=list(struct.unpack_from(f'<{n_extra}H', d, o + EXTRA)),
                    side=list(struct.unpack_from(f'<{n_side}H', d, o + N_SIDE + 4)),
                    stamp=struct.unpack_from('<6H', d, o + STAMP), tag=tag)

    def decks(self):
        return {i: self.deck(i) for i in range(NSLOTS) if self.in_use(i)}

    def free_slot(self):
        return next((i for i in range(NSLOTS) if not self.in_use(i)), None)

    def write_deck(self, slot, deck):
        """Write a deck; an empty slot gets the current time and a fresh tag unless the deck has
        them, an existing slot keeps its own. +0x98 and the trailing 62 bytes are untouched."""
        if not MAIN_MIN <= len(deck.main) <= MAIN_MAX or len(deck.extra) > EXTRA_MAX or len(deck.side) > SIDE_MAX:
            raise ValueError(f'deck size {len(deck.main)}/{len(deck.extra)}/{len(deck.side)} out of range')
        name = deck.name.encode('utf-16le') + b'\0\0'
        if len(name) > NAME_LEN:
            raise ValueError('deck name too long')
        o, d = self._off(slot), self.data
        if self.in_use(slot):
            old = self.deck(slot)
            stamp, tag = old.stamp, old.tag
        else:
            now = datetime.datetime.now()
            stamp = deck.stamp or (now.year, now.month, now.day, now.hour, now.minute, now.second)
            taken = {self.deck(i).tag for i in range(NSLOTS) if self.in_use(i)}
            tag = deck.tag or next(t for t in iter(lambda: random.randrange(1, 1 << 20), None) if t not in taken)
        struct.pack_into('<I', d, o + IN_USE, 1)
        d[o + NAME:o + NAME + NAME_LEN] = name.ljust(NAME_LEN, b'\0')
        struct.pack_into('<6H', d, o + STAMP, *stamp)
        struct.pack_into('<I', d, o + TAG, tag)
        struct.pack_into('<I', d, o + N_MAIN, len(deck.main))
        struct.pack_into('<I', d, o + N_EXTRA, len(deck.extra))
        d[o + MAIN:o + EXTRA] = struct.pack(f'<{len(deck.main)}H', *deck.main).ljust(EXTRA - MAIN, b'\0')
        d[o + EXTRA:o + N_SIDE] = struct.pack(f'<{len(deck.extra)}H', *deck.extra).ljust(N_SIDE - EXTRA, b'\0')
        struct.pack_into('<I', d, o + N_SIDE, len(deck.side))
        d[o + SIDE:o + SIDE + 0x1E] = struct.pack(f'<{len(deck.side)}H', *deck.side).ljust(0x1E, b'\0')

    def delete_deck(self, slot):
        """Free a deck slot the way the game does: clear the in-use flag and every field
        write_deck fills in (name through side). +0x0-0x4 and the trailing 62 bytes stay put."""
        o, d = self._off(slot), self.data
        struct.pack_into('<I', d, o + IN_USE, 0)
        d[o + NAME:o + SIDE + 0x1E] = b'\0' * (SIDE + 0x1E - NAME)

    # ---- trunk (read-only)
    def trunk(self, row):
        """(owned copies, copies allowed by the save's ban-list cache, low flag byte)."""
        a, b = struct.unpack_from('<HH', self.data, self.trunk_offset + row * 4)
        return (a >> 8) & 0x7F, b & 3, a & 0xFF

    def problems(self, deck, carddb, banlist=True):
        """Rule check: sizes, extra-deck card types, main+extra copies vs 3 / ban list / owned.
        `carddb` is anything with .cards, .row_of(num) and .name_of(num, default) (CardDB, CardSource).
        banlist=False ignores the save's ban list (for players who turned it off in the game)."""
        out = []
        if not MAIN_MIN <= len(deck.main) <= MAIN_MAX:
            out.append(f'main deck has {len(deck.main)} cards (40–60)')
        if len(deck.extra) > EXTRA_MAX:
            out.append(f'extra deck has {len(deck.extra)} cards (max 15)')
        if len(deck.side) > SIDE_MAX:
            out.append(f'side deck has {len(deck.side)} cards (max 15)')
        for sec, must_extra in ((deck.main, False), (deck.extra, True)):
            for n in set(sec):
                c = carddb.cards.get(n)
                if c is None:
                    out.append(f'card {n} is not in this game')
                elif c.attribute != '?' and c.extra_deck != must_extra:   # '?': type unknown without ISO
                    out.append(f'{c.name} belongs in the {"extra" if c.extra_deck else "main"} deck')
        # The game itself saved a deck with 3 in main + 1 in side ('sfby'), so the side deck
        # does not count toward the copy limit.
        copies = {}
        for n in deck.main + deck.extra:
            copies[n] = copies.get(n, 0) + 1
        for n, k in copies.items():
            row = carddb.row_of(n)
            if not row:
                continue
            owned, allowed, _ = self.trunk(row)
            allowed = allowed if banlist else 3
            cap = min(3, allowed, owned)
            if k > cap:
                name = carddb.name_of(n, str(n))
                out.append(f'{name} ×{k}, limit {cap} (ban list {allowed}, owned {owned})')
        return out
