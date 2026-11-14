"""Card database from a game's own `cardinfo_jpn.ehp` (TF6 `_J` members, TFSP `_R`).

CARD_Prop is 8 bytes per row, `<HBBHH`: v (card number in bits 0-13, +20 ATK in bit 15),
atk/40, def/20, f1, f2. In f1, bits 0-4 are a frame code and bit 5 a synchro/xyz/pendulum
modifier (both inferred from the card lists, 2026-10-27); attribute and level follow, one bit
higher on TFSP than on TF6. f2 bits 1-5 (TFSP 2-6) are the monster type (RACES).
"""
import re, struct
from dataclasses import dataclass

from . import ehp

FIRST_CARD = 3459
ATTRIBUTES = {1: 'LIGHT', 2: 'DARK', 3: 'WATER', 4: 'FIRE', 5: 'EARTH', 6: 'WIND', 7: 'DIVINE',
              8: 'SPELL', 9: 'TRAP'}
EXTRA_FRAMES = ('fusion', 'synchro', 'xyz', 'darksynchro')
# f2 monster-type code → type. Checked 2026-11-04 against ygocdb's race for every TF6 (3296) and
# TFSP (4538) monster it lists: one race per code, no exceptions. TFSP adds Wyrm at 22.
RACES = {1: '龙', 2: '不死', 3: '恶魔', 4: '炎', 5: '海龙', 6: '岩石', 7: '机械', 8: '鱼', 9: '恐龙', 10: '昆虫',
         11: '兽', 12: '兽战士', 13: '植物', 14: '水', 15: '战士', 16: '鸟兽', 17: '天使', 18: '魔法师', 19: '雷',
         20: '爬虫类', 21: '念动力'}
RACES_TF6 = {**RACES, 22: '幻神兽'}
RACES_TFSP = {**RACES, 22: '幻龙', 23: '幻神兽', 24: '创造神'}


@dataclass
class Card:
    num: int          # Konami card id: the value stored in decks
    row: int          # database row: the trunk index
    passcode: int     # 0 for game-only cards
    name: str
    text: str
    attribute: str    # LIGHT…DIVINE, or SPELL / TRAP
    frame: str        # normal effect fusion synchro darksynchro xyz ritual pendulum token spell trap
    level: int        # level/rank for monsters; a subtype code for spells and traps
    atk: int
    defense: int
    arts: int = 1     # artworks available (alternate arts > 1)
    game_only: bool = False   # game/anime-original card: no real-world passcode
    tuner: int = 0            # 1 Tuner, 2 Dark Tuner (the game's anime ＤＴ cards)
    race: str = ''            # monster type (龙, 战士…); '' for spells, traps and unknown

    @property
    def is_monster(self):
        return self.attribute not in ('SPELL', 'TRAP')

    @property
    def extra_deck(self):
        return self.frame in EXTRA_FRAMES


# (code, modifier) → frame. Checked 2026-10-28 against ygocdb's card types for every TF6 and TFSP
# monster that has a real-world counterpart (codes 9/11 + modifier are the game's Dark Tuners /
# Dark Synchros, which ygocdb lacks).
_FRAMES = {(1, 0): 'normal', (31, 0): 'normal', (5, 0): 'fusion', (7, 0): 'fusion',
           (9, 0): 'ritual', (11, 0): 'ritual', (21, 0): 'token',
           (3, 1): 'synchro', (5, 1): 'synchro', (7, 1): 'synchro', (11, 1): 'darksynchro',
           (13, 1): 'xyz', (15, 1): 'xyz', (19, 1): 'pendulum', (21, 1): 'pendulum'}


def _frame(attribute, code, mod, flag6=False):
    """flag6: TFSP's extra bit 6 (free once its fields moved up a bit); set on 影依猎鹰, a
    normal-coded card that is really an effect monster."""
    if attribute == 'SPELL':
        return 'spell'
    if attribute == 'TRAP':
        return 'trap'
    frame = _FRAMES.get((code, int(mod)), 'effect')
    return 'effect' if frame == 'normal' and flag6 else frame


def _stat(tens):
    """ATK/DEF are 9-bit values in tens (atk: low 7 bits of the atk byte << 2 | top 2 bits of the
    card-number word; def: def byte << 1 | top bit of the atk byte). 511 = "?" → -1. Checked
    2026-10-28 against ygocdb for every real monster in TF6 and TFSP."""
    return -1 if tens == 511 else tens * 10


# Tuner codes, checked 2026-10-28 against ygocdb's Tuner flag (TFSP adds 29 + modifier).
_TUNERS = {(1, 1), (7, 1), (31, 0), (29, 1)}


def _tuner(attribute, code, mod):
    if attribute in ('SPELL', 'TRAP'):
        return 0
    if (code, int(mod)) == (9, 1):
        return 2
    return 1 if (code, int(mod)) in _TUNERS else 0


def huffman_text(desc, huff, bitpos):
    """CARD_Desc: MSB-first bits walk CARD_Huff nodes (u16 child for bit 0, u16 for bit 1);
    a node whose child is 0 is a leaf with its UTF-16 char at +4, and the bit that reached it
    is read again from the root. U+0000 ends the text (algorithm from ogy by Sten Feldman, BSD-2-Clause; see CREDITS.md)."""
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


def _utf16z(buf, off):
    end = off
    while buf[end:end + 2] != b'\0\0':
        end += 2
    return buf[off:end].decode('utf-16le', 'replace')


class CardDB:
    def __init__(self, cardinfo_bytes):
        m = ehp.members(cardinfo_bytes)
        self.suffix = '_J' if 'CARD_Name_J.bin' in m else '_R'
        shift = 0 if self.suffix == '_J' else 1
        races = RACES_TF6 if shift == 0 else RACES_TFSP
        names, indx = m[f'CARD_Name{self.suffix}.bin'], m[f'CARD_Indx{self.suffix}.bin']
        desc, huff = m[f'CARD_Desc{self.suffix}.bin'], m[f'CARD_Huff{self.suffix}.bin']
        prop, pas, intid = m['CARD_Prop.bin'], m['CARD_Pass.bin'], m['CARD_IntID.bin']
        self.intid = intid
        self.cards = {}
        for row in range(len(prop) // 8):
            v, atk, dfn, f1, f2 = struct.unpack_from('<HBBHH', prop, row * 8)
            num = v & 0x3FFF
            if not num:
                continue
            attribute = ATTRIBUTES.get((f1 >> (6 + shift)) & 0xF, '?')
            name = re.sub(r'\$C\d', '', _utf16z(names, struct.unpack_from('<I', indx, row * 8)[0]))
            self.cards[num] = Card(
                num=num, row=row, passcode=struct.unpack_from('<I', pas, row * 4)[0],
                name=name, text=huffman_text(desc, huff, struct.unpack_from('<I', indx, row * 8 + 4)[0]),
                attribute=attribute, frame=_frame(attribute, f1 & 0x1F, bool(f1 & 0x20), shift and bool(f1 & 0x40)),
                level=(f1 >> (10 + shift)) & (0x3F >> shift), atk=_stat(((atk & 0x7F) << 2) | (v >> 14)),
                defense=_stat((dfn << 1) | (atk >> 7)))
            self.cards[num].game_only = self.cards[num].passcode == 0
            self.cards[num].tuner = _tuner(attribute, f1 & 0x1F, bool(f1 & 0x20))
            if attribute not in ('SPELL', 'TRAP'):
                self.cards[num].race = races.get((f2 >> (1 + shift)) & 0x1F, '')
        # `$mNNNN` in a text is the name of card NNNN. Unknown numbers are left as they are
        # (the TF6 CN patch has one typo, "$m40641" in card 3728, meant as Dark Magician).
        for c in self.cards.values():
            c.text = re.sub(r'\$m(\d+)', lambda mm: self.name_of(int(mm.group(1)), mm.group(0)), c.text)

    def name_of(self, num, default=None):
        c = self.cards.get(num)
        return c.name if c else default

    def row_of(self, num):
        """Trunk index for a card number (CARD_IntID), 0 if the game lacks the card."""
        i = num - FIRST_CARD
        if not 0 <= i < len(self.intid) // 2:
            return 0
        return struct.unpack_from('<H', self.intid, i * 2)[0]

    def by_passcode(self):
        return {c.passcode: c for c in self.cards.values() if c.passcode}
