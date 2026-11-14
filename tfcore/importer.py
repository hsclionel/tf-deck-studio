"""Deck import from text: YDK files, ydke:// links and free-form lists such as forum posts.

Pipeline: parse lines into (section, name or passcode, count) → match each name against every
name the card source knows (ROM, ygocdb CN/SC/JP/EN, remembered aliases) → adjust for the game
(route extra-deck cards, cap copies by the save's ban list and owned counts) → report.
Nothing is written to a save here; the editor shows the result for review first.
"""
import base64, difflib, json, os, re, struct, unicodedata
from collections import defaultdict
from dataclasses import dataclass, field

from . import ygocdb

SECTIONS = ('main', 'extra', 'side')
_HEADER_WORDS = {
    'main': ('构筑', '構築', '主卡组', '主卡組', '主牌组', '卡组', 'main', 'maindeck', 'deck',
             '怪兽', '怪獸', '怪兽卡', '怪獸卡', '魔法', '魔法卡', '陷阱', '陷井', '陷阱卡',
             'monster', 'monsters', 'spell', 'spells', 'trap', 'traps',
             'monstercard', 'monstercards', 'spellcard', 'spellcards', 'magic', 'magiccards', 'trapcard', 'trapcards',
             'maindeckcards'),
    'extra': ('额外', '額外', '额外卡组', '額外卡組', '额外牌组', 'ex', 'ex卡组', 'ex卡組', 'extra', 'extradeck', '融合',
              'extradeckcards', 'extracards'),
    'side': ('副卡组', '副卡組', '副卡', '副牌组', 'side', 'sidedeck', '备牌', '備牌', 'sidedeckcards', 'sidecards'),
}
# What a header says about the cards under it (used to break ties between candidates).
_HEADER_KIND = {**{w: 'monster' for w in ('怪兽', '怪獸', '怪兽卡', '怪獸卡', 'monster', 'monsters', 'monstercard',
                                          'monstercards')},
                **{w: 'spell' for w in ('魔法', '魔法卡', 'spell', 'spells', 'spellcard', 'spellcards', 'magic',
                                        'magiccards')},
                **{w: 'trap' for w in ('陷阱', '陷井', '陷阱卡', 'trap', 'traps', 'trapcard', 'trapcards')},
                **{w: 'extra' for w in ('额外', '額外', '额外卡组', '額外卡組', '额外牌组', 'ex', 'ex卡组', 'ex卡組',
                                        'extra', 'extradeck', '融合', 'extradeckcards', 'extracards')}}
_SEPARATORS = r'[\s·・•\-－—―‐_.,，。、!！?？「」『』"“”\'‘’:：/／\\]'


# Japanese/traditional forms the CN patches kept in some names → simplified.
_VARIANTS = str.maketrans({**dict(zip('呪縛時異間増穂鵺玛', '咒缚时异间增穗夜马')),   # 西格玛 = 西格马
                           '罪': 'sin'})        # community "罪 星尘龙" = ROM "Ｓｉｎ 星尘龙"
_WORDS = (('黑羽', 'bf'),)                        # Blackwing: TF6 patch "ＢＦ－", TFSP patch "黑羽－"
ATTR_CHAR = {'光': 'LIGHT', '暗': 'DARK', '炎': 'FIRE', '火': 'FIRE', '地': 'EARTH', '水': 'WATER',
             '风': 'WIND', '風': 'WIND', '神': 'DIVINE'}
# Notes that mean "the game's anime version", e.g. 百眼龙（黑暗同调）.
_GAME_VERSION_HINTS = ('黑暗同调', '暗黑同调', '黑暗同步', '暗黑同步', 'darksynchro', '动画', '動畫', 'anime')


def norm(s):
    """Comparison key: NFKC, variants, lower case, separators removed ('Ｅ·ＨＥＲＯ　天空侠' → 'ehero天空侠')."""
    s = unicodedata.normalize('NFKC', s).translate(_VARIANTS)
    for a, b in _WORDS:
        s = s.replace(a, b)
    return re.sub(_SEPARATORS, '', s).lower()


def notes_of(s):
    return ''.join(re.findall(r'[（(\[【［](.*?)[）)\]】］]', s))


def strip_notes(s):
    """Drop bracketed notes: '百眼龙（黑暗同调）' → '百眼龙'."""
    return re.sub(r'[（(\[【［].*?[）)\]】］]', '', s).strip()


@dataclass
class Line:
    raw: str
    section: str
    count: int
    text: str = ''              # card name as written
    passcode: int = 0           # YDK / ydke entries
    num: int = 0                # matched card number (0 = unresolved)
    score: float = 0.0
    candidates: list = field(default_factory=list)   # [(num, score)] best first
    kind: str = ''              # 'monster' / 'spell' / 'trap' / 'extra' from the header above the line
    note: str = ''
    comment: bool = False       # a remark in the list, not a card (shown, never imported)


@dataclass
class ImportResult:
    lines: list
    main: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    side: list = field(default_factory=list)
    adjustments: list = field(default_factory=list)  # human-readable changes made for the game
    cuts: list = field(default_factory=list)         # [(num, section, copies lost, why)] from copy limits
    warnings: list = field(default_factory=list)

    @property
    def unresolved(self):
        return [ln for ln in self.lines if not ln.num and not ln.comment]


# ---------------------------------------------------------------- parsing

def _header(line):
    """(section, expected count, label) when the line is a section header, else None.
    Any '【…】' line with an optional count ('【怪兽卡】*16', '【额外】15') is a header; unknown labels
    keep the current section (section None)."""
    m = re.fullmatch(r'[【\[［]\s*([^【】\[\]［］]+?)\s*[】\]］]\s*[:：]?\s*[\*xX×✕]?\s*(\d*)\s*', line)
    if not m:
        m = re.fullmatch(r'[#!]?\s*([^\d【】\[\]［］()（）*]+?)\s*[:：]?\s*[\*xX×✕]?\s*(\d*)\s*', line)
        if not m or not _known(norm(m.group(1))):
            return None
    word = norm(m.group(1))
    return _known(word), int(m.group(2)) if m.group(2) else None, word


def _known(word):
    for sec, words in _HEADER_WORDS.items():
        if word in {norm(w) for w in words}:
            return sec
    return None


def _count_and_name(line):
    for pat in (r'(?P<name>.+?)\s*[\*xX×✕]\s*(?P<n>\d{1,2})',      # 名字*3, Name x3
                r'(?P<n>\d{1,2})\s*[\*xX×✕]?\s+(?P<name>.+)',        # 3 Name, 3x Name
                r'(?P<n>\d{1,2})\s*[\*xX×✕]\s*(?P<name>.+)'):        # 3x名字
        m = re.fullmatch(pat, line)
        if m and 0 < int(m.group('n')) <= 9:
            return int(m.group('n')), m.group('name').strip()
    return 1, line


def _ydke(text):
    m = re.search(r'ydke://([A-Za-z0-9+/=]*)!([A-Za-z0-9+/=]*)!([A-Za-z0-9+/=]*)!?', text)
    if not m:
        return None
    lines = []
    for sec, b64 in zip(SECTIONS, m.groups()):
        raw = base64.b64decode(b64) if b64 else b''
        counts = defaultdict(int)
        for (pc,) in struct.iter_unpack('<I', raw[:len(raw) // 4 * 4]):
            counts[pc] += 1
        lines += [Line(f'{pc}', sec, k, passcode=pc) for pc, k in counts.items()]
    return lines


def parse(text):
    """(lines, headers): lines with section headers applied; headers = [{label, section,
    expected, listed}] for every header that states a count (to check the list against it)."""
    text = unicodedata.normalize('NFKC', text)
    ydke = _ydke(text)
    if ydke is not None:
        return ydke, []
    section, headers, lines = 'main', [], []
    current, kind = None, ''
    is_ydk = bool(re.search(r'^\s*#main\b', text, re.M))
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith(('//', '#created')):
            continue
        h = _header(s)
        if h:
            sec, expected, label = h
            section = sec or section
            kind = _HEADER_KIND.get(label, kind if sec is None else '')
            current = dict(label=label, section=section, expected=expected, listed=0)
            if expected is not None:
                headers.append(current)
            continue
        if is_ydk and re.fullmatch(r'\d{4,9}', s):
            lines.append(Line(s, section, 1, passcode=int(s)))
            continue
        remark = ''
        m = re.fullmatch(r'(.*?[\*xX×✕]\s*\d{1,2})\s*[（(]([^（）()]*)[）)]\s*', s)
        if m:                                        # 'X*1（可带2）': the note after the count is a remark
            s, remark = m.group(1), m.group(2)
        n, name = _count_and_name(s)
        if n == 1 and name == s and (re.search(r'[，,。；;！!？?]', name) or len(norm(name)) > 16):
            lines.append(Line(raw.strip(), section, 0, text=name, comment=True, note='备注，不是卡名'))
            continue
        lines.append(Line(raw.strip(), section, n, text=name, note=remark, kind=kind))
        if current is not None:
            current['listed'] += n
    if is_ydk:   # one line per copy in YDK: merge
        merged = {}
        for ln in lines:
            key = (ln.section, ln.passcode or ln.text)
            if key in merged:
                merged[key].count += ln.count
            else:
                merged[key] = ln
        lines = list(merged.values())
    return lines, headers


# ---------------------------------------------------------------- matching

class NameIndex:
    """Every name the source knows → card numbers, with a character index for fuzzy lookups."""

    def __init__(self, source, aliases=None):
        self.source = source
        self.keys = defaultdict(set)             # normalized name → {num}
        for num, c in source.cards.items():
            for name in [c.name, *source.alt_names.get(num, {}).values()]:
                if name:
                    self.keys[norm(name)].add(num)
                    self.keys[norm(strip_notes(name))].add(num)
        self.aliases = {norm(k): v for k, v in (aliases or {}).items() if v in source.cards}
        for key, num in self.aliases.items():      # nicknames also take part in fuzzy matching
            self.keys[key].add(num)
        self.by_char = defaultdict(set)
        for key in self.keys:
            for ch in set(key):
                self.by_char[ch].add(key)
        self.by_passcode = {c.passcode: n for n, c in source.cards.items() if c.passcode}

    def _order(self, nums, prefer_game):
        """Same-name cards (anime/game versions): real cards first unless a note asks for the game one."""
        return sorted(nums, key=lambda n: (self.source.cards[n].game_only != prefer_game, n))

    def match(self, text, limit=3):
        """[(num, score)] best first. 1.0 exact; 0.97 exact after dropping a note; 0.9 when several
        same-name cards fit; 0.95 attribute shorthand ('命运女郎·光'); below that fuzzy."""
        base = strip_notes(text) or text
        q_full, q = norm(text), norm(base)
        if not q:
            return []
        for key in (q_full, q):
            if key in self.aliases:
                return [(self.aliases[key], 1.0)]
        hint = norm(notes_of(text))
        prefer_game = any(norm(h) in hint for h in _GAME_VERSION_HINTS) if hint else False
        for key, score in ((q_full, 1.0), (q, 0.97)):
            if key in self.keys:
                nums = self._order(self.keys[key], prefer_game)
                if len(nums) > 1 and not hint:
                    score = 0.9
                return [(n, score) for n in nums][:limit]
        m = re.fullmatch(r'(.+?)[·・\s]*([' + ''.join(ATTR_CHAR) + '])', base)
        if m and len(norm(m.group(1))) >= 2:
            prefix, attr = norm(m.group(1)), ATTR_CHAR[m.group(2)]
            nums = sorted({n for key, ns in self.keys.items() if key.startswith(prefix) for n in ns
                           if self.source.cards[n].attribute == attr})
            if nums:
                score = 0.95 if len(nums) == 1 else 0.85
                return [(n, score) for n in self._order(nums, prefer_game)][:limit]
        # fuzzy: keys sharing enough characters, ranked by sequence similarity
        hits = defaultdict(int)
        for ch in set(q):
            for key in self.by_char.get(ch, ()):
                hits[key] += 1
        need = max(1, len(set(q)) // 2)
        scored = []
        for key, shared in hits.items():
            if shared < need:
                continue
            r = difflib.SequenceMatcher(None, q, key).ratio()
            if q in key:                       # a shortened name: '神圣防护罩反射镜' ⊂ '神圣防护罩反射镜力'
                r = max(r, 0.75 + 0.25 * len(q) / len(key))
            elif key in q:                     # extra words around a real name may change the card: confirm
                r = min(r, AUTO_ACCEPT - 0.02)
            scored.append((r, key))
        out = {}
        for r, key in scored:
            for n in self.keys[key]:
                if prefer_game and self.source.cards[n].game_only:
                    r2 = min(0.95, r + 0.1)          # the note asked for the game version
                else:
                    r2 = r
                out[n] = max(out.get(n, 0), round(r2, 3))
        ranked = sorted(out.items(), key=lambda kv: (-kv[1], self.source.cards[kv[0]].game_only != prefer_game, kv[0]))
        return ranked[:limit]


# ---------------------------------------------------------------- pipeline

AUTO_ACCEPT = 0.82          # below this a line stays unresolved until the user picks a candidate


_OUTSIDE = {}


def _outside_index(names_db):
    """normalized name → (cid, display name) for every real card (to explain cards a game lacks)."""
    key = id(names_db)
    if key not in _OUTSIDE:
        idx = {}
        for cid, e in names_db.items():
            for _, f in ygocdb.NAME_FIELDS:
                if e.get(f):
                    idx.setdefault(norm(e[f]), (cid, e.get('cn_name') or e[f]))
                    idx.setdefault(norm(strip_notes(e[f])), (cid, e.get('cn_name') or e[f]))
        _OUTSIDE.clear()
        _OUTSIDE[key] = idx
    return _OUTSIDE[key]


def _fits(card, kind):
    if kind == 'spell':
        return card.attribute == 'SPELL'
    if kind == 'trap':
        return card.attribute == 'TRAP'
    if kind == 'monster':
        return card.attribute not in ('SPELL', 'TRAP') and not card.extra_deck
    if kind == 'extra':
        return card.extra_deck
    return True


def _by_kind(cands, kind, source):
    """Break ties with the header: under 【魔法】 a spell beats an equally similar monster."""
    if not kind or not cands:
        return cands
    def bonus(s):           # a nudge between candidates, never enough to cross the auto-accept line
        return min(s + 0.03, AUTO_ACCEPT - 0.01) if s < AUTO_ACCEPT else min(1.0, s + 0.03)
    adj = [(n, round(bonus(s) if _fits(source.cards[n], kind) and s < 0.97 else
                     s - 0.05 if not _fits(source.cards[n], kind) and source.cards[n].attribute != '?' else s, 3))
           for n, s in cands]
    return sorted(adj, key=lambda x: -x[1])


def builtin_alternates():
    """Other passcodes of cards in TF6/TFSP (reprints, alternate artwork) → card number, shipped as
    tfcore/passcodes_alt.json (numbers only; `cli passcodes` regenerates it)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'passcodes_alt.json')
    with open(path, encoding='utf-8') as f:
        return {int(k): v for k, v in json.load(f).items() if not k.startswith('_')}


def builtin_nicknames():
    """Community nicknames shipped with the app (tfcore/nicknames.json): name → card number."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nicknames.json')
    with open(path, encoding='utf-8') as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith('_')}


def standins(cards):
    """[(real num, stand-in num, names, passcode)] for real cards this game lacks but has a
    same-effect original of (tfcore/standins.json)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'standins.json')
    with open(path, encoding='utf-8') as f:
        table = {int(k): v for k, v in json.load(f).items() if not k.startswith('_')}
    return [(real, e['to'], e['names'], e.get('passcode', 0)) for real, e in table.items()
            if real not in cards and e['to'] in cards]


def run(text, source, aliases=None, trunk=None, names_db=None, passcodes=None):
    """Parse and match `text`. `trunk(num)` → (owned, allowed) or None, for the copy caps.
    With `names_db` (ygocdb), a real card the game does not have is reported instead of guessed.
    `passcodes` (passcode -> game number) covers other passcodes of cards the game has."""
    lines, headers = parse(text)
    known = {k: v for k, v in builtin_nicknames().items() if v in source.cards}
    subs = standins(source.cards)
    known.update({name: to for _, to, names, _ in subs for name in names})
    by_passcode = {**{pc: n for pc, n in builtin_alternates().items() if n in source.cards},
                   **{pc: to for _, to, _, pc in subs if pc}}
    index = NameIndex(source, {**known, **(aliases or {})})
    outside = _outside_index(names_db) if names_db else {}
    for ln in lines:
        if ln.comment:
            continue
        if ln.passcode:
            num = index.by_passcode.get(ln.passcode) or by_passcode.get(ln.passcode) or (passcodes or {}).get(ln.passcode)
            ln.num, ln.score = (num, 1.0) if num else (0, 0.0)
            if not num:
                ln.note = '本游戏没有这张卡'
            continue
        ln.candidates = _by_kind(index.match(ln.text, limit=5), ln.kind, source)[:3]
        if ln.candidates and ln.candidates[0][1] >= 0.97:
            ln.num, ln.score = ln.candidates[0]
            continue
        hit = outside.get(norm(ln.text)) or outside.get(norm(strip_notes(ln.text)))
        if hit and hit[0] not in source.cards:
            ln.note = f'「{hit[1]}」是真实存在的卡，但本游戏没有'
            ln.score = ln.candidates[0][1] if ln.candidates else 0.0
            continue
        if ln.candidates and ln.candidates[0][1] >= AUTO_ACCEPT:
            ln.num, ln.score = ln.candidates[0]
            if len(ln.candidates) > 1 and ln.candidates[0][1] - ln.candidates[1][1] < 0.01:
                ln.note = (ln.note + '；' if ln.note else '') + '有几张卡一样像，请确认'
                ln.score = min(ln.score, 0.9)
        elif ln.candidates:
            ln.score = ln.candidates[0][1]
    return finish(lines, headers, source, trunk)


def finish(lines, headers, source, trunk=None):
    """Build the deck from resolved lines (call again after the user resolves more)."""
    res = ImportResult(lines)
    copies = defaultdict(int)
    subs = {to: (real, {norm(n) for n in names}, pc) for real, to, names, pc in standins(source.cards)}
    for ln in lines:
        if not ln.num:
            continue
        card = source.cards[ln.num]
        if ln.num in subs and (norm(ln.text) in subs[ln.num][1] or ln.passcode and ln.passcode == subs[ln.num][2]):
            res.adjustments.append(f'{ln.text or ln.passcode}：本游戏没有这张卡，换成同效果的「{card.name}」')
        sec = ln.section
        if sec in ('main', 'extra') and card.attribute != '?':
            want = 'extra' if card.extra_deck else 'main'
            if want != sec:
                res.adjustments.append(f'{card.name}：属于{"额外卡组" if want == "extra" else "主卡组"}，已移过去')
                sec = want
        k = ln.count
        if sec != 'side':
            cap = 3
            t = trunk(ln.num) if trunk else None
            if t:
                owned, allowed = t
                cap = min(3, owned, allowed)
            left = max(0, cap - copies[ln.num])
            if k > left:
                why = '禁止卡' if t and t[1] == 0 else f'限制 {cap} 张' if t and t[1] < 3 else \
                      f'只持有 {t[0]} 张' if t and t[0] < 3 else '最多 3 张'
                res.adjustments.append(f'{card.name}：{k} → {left}（{why}）')
                res.cuts.append((ln.num, sec, k - left, why))
                k = left
            copies[ln.num] += k
        getattr(res, sec).extend([ln.num] * k)
    whole = {norm(w) for w in ('构筑', '構築', 'deck', '卡组', '主卡组', '主卡組', '主牌组', 'main', 'maindeck')}
    for h in headers:
        if h['label'] in whole:
            continue      # a whole-deck total ("【构筑】40") is checked against the main deck below
        if h['listed'] != h['expected']:
            res.warnings.append(f'「{h["label"]}」标的是 {h["expected"]} 张，实际列了 {h["listed"]} 张')
    for h in headers:
        if h['label'] in whole:
            listed = sum(ln.count for ln in lines if ln.section == 'main')
            if listed != h['expected']:
                res.warnings.append(f'「{h["label"]}」标的是 {h["expected"]} 张，主卡组实际列了 {listed} 张')
    if not 40 <= len(res.main) <= 60:
        res.warnings.append(f'主卡组现在 {len(res.main)} 张，需要 40–60 张')
    return res


# ---------------------------------------------------------------- export

def to_ydk(deck, cards):
    """YDK text; cards without a passcode (game-original) are listed as comments."""
    out = ['#created by TF Deck Studio', '#main']
    for sec, header in (('main', None), ('extra', '#extra'), ('side', '!side')):
        if header:
            out.append(header)
        for n in getattr(deck, sec):
            c = cards.get(n)
            out.append(str(c.passcode) if c and c.passcode else f'# {n} {c.name if c else ""} (no passcode)')
    return '\n'.join(out) + '\n'


def to_text(deck, cards):
    """Plain list in the same style as forum posts: 【主卡组】40 / 名字*3."""
    out = []
    for sec, label in (('main', '主卡组'), ('extra', '额外'), ('side', '副卡组')):
        nums = getattr(deck, sec)
        if not nums:
            continue
        out.append(f'【{label}】{len(nums)}')
        counted = {}
        for n in nums:
            counted[n] = counted.get(n, 0) + 1
        out += [f'{cards[n].name if n in cards else n}*{k}' for n, k in counted.items()]
        out.append('')
    return '\n'.join(out)
