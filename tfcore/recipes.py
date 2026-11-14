"""The game's own deck recipes, read from the user's ISO.

TFSP keeps them in an EHP archive embedded in EBOOT.BIN (the PLAY CN patch ships that ELF
decrypted; an encrypted ~PSP EBOOT yields nothing): RCP000.ydc … RCP840.ydc plus
recipe_name_<lang>.bin. A .ydc is an 8-byte header, then u16 count + u16 card numbers for main,
extra and side in turn. String tables (recipe_name_*, chr_name_*) are u32 count, u32 index offset,
u32 text base, then per-string u32 byte offsets to UTF-16 text.

Which character owns which recipes comes from two tables in the executable (mapped 2026-10-28):
16-byte rows (u32 character id, u32 first recipe, u32 count, 0) starting with the player's three
starters (1, 0, 3, 0), and 164-byte character rows with the id at +4, a pointer to the asset
prefix (e.g. "KAIBA_00_0") at +8 and the chr_name index of the full name at +80. Characters own
four recipes, weakest first; recipes after the last character are the game's special decks.
"""
import json, os, struct
from dataclasses import asdict, dataclass, field

from . import ehp, iso

FORMAT = 1
EBOOT = 'PSP_GAME/SYSDIR/EBOOT.BIN'
_CHR_ROW, _CHR_ID, _CHR_PTR, _CHR_NAME = 164, 4, 8, 80

# Decks after the character recipes, by recipe index (TFSP).
SPECIAL = ((771, 777, 'repro', '再现卡组'), (777, 783, 'wcs', 'WCS 冠军卡组'), (783, 789, 'meta', '认真卡组'),
           (789, 798, 'starter', '入门预组'), (798, 834, 'structure', '构筑预组'), (834, 841, 'pack', '特别套装'))
CATEGORY_LABEL = {'starter0': '初期卡组', 'character': '角色卡组', **{k: v for _, _, k, v in SPECIAL}}


@dataclass
class Recipe:
    index: int
    name: str
    category: str                 # starter0 character repro wcs meta starter structure pack
    character: str = ''
    level: int = 0                # 1..4 for character decks (4 = the character's strongest)
    main: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    side: list = field(default_factory=list)

    @property
    def champion(self):
        """The strong end of the catalog: tournament winners, meta decks, characters at level 4."""
        return self.category in ('wcs', 'meta', 'repro') or self.level == 4


def strings(b):
    n, table, base = struct.unpack_from('<III', b, 0)
    out = []
    for i in range(n):
        start = end = base + struct.unpack_from('<I', b, table + 4 * i)[0]
        while end + 1 < len(b) and b[end:end + 2] != b'\0\0':
            end += 2
        out.append(b[start:end].decode('utf-16le', 'replace'))
    return out


def ydc(b):
    pos, parts = 8, []
    for _ in range(3):
        n = struct.unpack_from('<H', b, pos)[0]
        parts.append(list(struct.unpack_from(f'<{n}H', b, pos + 2)))
        pos += 2 + 2 * n
    return parts


def _archives(elf):
    """Every EHP archive embedded in the executable, as {member: bytes}."""
    magic, pos = struct.pack('<I', ehp.MAGIC), 0
    while (pos := elf.find(magic, pos)) >= 0:
        size = struct.unpack_from('<I', elf, pos + 4)[0]
        try:
            yield ehp.members(elf[pos:pos + size])
        except (ValueError, struct.error, UnicodeDecodeError):
            pass
        pos += 4


def _lang(members, stem):
    """The CN patch writes its text into the Japanese slot."""
    for lang in ('j', 'e'):
        if f'{stem}_{lang}.bin' in members:
            return strings(members[f'{stem}_{lang}.bin'])
    return []


def _owners(elf, chr_names):
    """{character id: (first recipe, count, name)} or {} when the tables are not found."""
    p = elf.find(struct.pack('<8I', 1, 0, 3, 0, 2, 3, 4, 0))
    if p < 0:
        return {}
    ranges = {}
    while p + 16 <= len(elf):
        cid, first, count, zero = struct.unpack_from('<4I', elf, p)
        if zero or count > 16 or (ranges and cid != max(ranges) + 1):
            break
        ranges[cid] = (first, count)
        p += 16
    names = {}
    phoff = struct.unpack_from('<I', elf, 0x1C)[0]
    seg_off, seg_vaddr = struct.unpack_from('<II', elf, phoff + 4)       # first loadable segment
    asset = elf.find(b'KAIBA_00_0\0')
    ptr = elf.find(struct.pack('<I', asset - seg_off + seg_vaddr)) if asset > 0 else -1
    if ptr > 0 and chr_names:
        row = ptr - _CHR_PTR
        while row - _CHR_ROW >= 0 and 0 < struct.unpack_from('<I', elf, row - _CHR_ROW + _CHR_NAME)[0] < len(chr_names):
            row -= _CHR_ROW
        while row + _CHR_ROW <= len(elf):
            cid, name = struct.unpack_from('<I', elf, row + _CHR_ID)[0], struct.unpack_from('<I', elf, row + _CHR_NAME)[0]
            if not 0 < name < len(chr_names) or cid > 1000:
                break
            names[cid] = chr_names[name].replace('　', ' ')
            row += _CHR_ROW
    return {cid: (first, count, names.get(cid, '')) for cid, (first, count) in ranges.items()}


def extract(elf):
    """All recipes in a decrypted TFSP EBOOT, or [] when there are none to read."""
    if elf[:4] != b'\x7fELF':
        return []
    rcp = chrs = None
    for members in _archives(elf):
        if 'RCP000.ydc' in members:
            rcp = members
        elif any(k.startswith('chr_name_') for k in members):
            chrs = members
    if not rcp:
        return []
    names = _lang(rcp, 'recipe_name')
    owner = {}
    for cid, (first, count, who) in _owners(elf, _lang(chrs, 'chr_name') if chrs else []).items():
        for k in range(count):
            owner[first + k] = (who, k + 1) if cid > 1 else ('', 0)
    out = []
    for i in range(len(names)):
        data = rcp.get(f'RCP{i:03d}.ydc')
        if not data:
            continue
        main, extra, side = ydc(data)
        cat = next((c for lo, hi, c, _ in SPECIAL if lo <= i < hi), None)
        who, level = owner.get(i, ('', 0))
        if cat is None:
            cat = 'starter0' if i in owner and not level else 'character'
        out.append(Recipe(i, names[i], cat, who, level, main, extra, side))
    return out


def from_iso(path):
    return extract(iso.fetch(iso.open_iso(path), EBOOT))


def save(recipes, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'format': FORMAT, 'recipes': [asdict(r) for r in recipes]}, f, ensure_ascii=False)


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        meta = json.load(f)
    if meta.get('format') != FORMAT:
        return None
    return [Recipe(**r) for r in meta['recipes']]
