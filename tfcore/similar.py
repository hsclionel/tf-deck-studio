"""Cards with a similar effect, to fill copies a ban list or the collection cuts from a deck.

No embeddings needed: a game has 5–7k cards, so each query scores every candidate in memory from
the same card type (main/extra monster, spell, trap), the role tags (tfcore.tags), character bigrams
of the Chinese effect text, an archetype word shared in the name, and frame/attribute/level.
"""
import re
from collections import Counter

from . import tags

_TEXT_CACHE = {}
_NOISE = re.compile(r'[\s\d０-９①-⑩「」『』（）()：:，,。.、・·\-－—!！?？●]+')
_SPLIT = re.compile(r'[・·\-－　 ]')


def _kind(c):
    if c.attribute in ('SPELL', 'TRAP'):
        return c.attribute
    return 'extra' if c.extra_deck else 'main'


def _bigrams(cards):
    """num → (character bigrams, characters) of the effect text (cached per card table). The plain
    character set matches the same effect in old and new wording (TF6 「场上存在的全部怪兽破坏」 vs
    TFSP 「场上的怪兽全部破坏」), where word order breaks the bigrams."""
    key = id(cards)
    if key not in _TEXT_CACHE:
        out = {}
        for n, c in cards.items():
            t = _NOISE.sub('', re.sub(r'「[^」]*」|存在', '', c.text or ''))   # card names in quotes say little
            out[n] = ({t[i:i + 2] for i in range(len(t) - 1)}, set(t))
        _TEXT_CACHE.clear()
        _TEXT_CACHE[key] = out
    return _TEXT_CACHE[key]


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _archetypes(card):
    """Archetype words for a card: the leading word of a name like 'Ｅ·ＨＥＲＯ　天空侠' / '六武众－伊郎',
    and every 「X」 its text calls an archetype ('名字带有「六武众」的怪兽')."""
    parts = [p for p in _SPLIT.split(card.name) if p]
    out = {parts[0]} if len(parts) > 1 and len(parts[0]) >= 2 else set()
    out.update(re.findall(r'名字带有「([^」]{2,})」', card.text or ''))
    return out


_HITS = (('monster', re.compile(r'怪兽全部|全部怪兽')), ('spelltrap', re.compile(r'魔法.{0,2}陷阱.{0,2}全部')))
_NARROW = re.compile(r'(?:族|属性)怪兽全部|全部.{0,4}(?:族|属性)怪兽')


def _hits(card):
    """What a mass-removal effect hits: Raigeki and Harpie's Feather Duster share the 全场破坏 tag."""
    return {k for k, p in _HITS if p.search(card.text or '')}


def _narrow(card):
    """A wipe limited to one type or attribute (永远的渴水: fish only, 战士抹杀: warriors only)."""
    return bool(_NARROW.search(card.text or ''))


def _shares(arch, card):
    return next((a for a in arch if a in card.name), None)


def similar(num, cards, room, limit=6):
    """[(num, score, reasons)] best first: cards like `num` that still have room in the deck.
    `room(n)` → copies of n that may still be added (ban list, owned count, copies already used)."""
    base = cards.get(num)
    if base is None or base.attribute == '?':
        return []
    kind, grams = _kind(base), _bigrams(cards)
    roles = tags.from_text(base) - {'tuner'}
    arch = _archetypes(base)
    hits, narrow, staples = _hits(base), _narrow(base), tags.staples()
    out = []
    for n, c in cards.items():
        if n == num or c.attribute == '?' or c.frame == 'token' or _kind(c) != kind or room(n) <= 0:
            continue
        text =0.6 * _jaccard(grams[num][0], grams[n][0]) + 0.4 * _jaccard(grams[num][1], grams[n][1])
        if text < 0.12:
            continue
        theirs = tags.from_text(c) - {'tuner'}           # the Tuner rule below handles that
        shared = roles & theirs
        score = 0.55 * text + 0.3 * _jaccard(roles, theirs)
        reasons = [tags.TAGS[t] for t in tags.TAGS if t in shared]
        same = _shares(arch, c) or _shares(_archetypes(c), base)
        if same:
            score += 0.15
            reasons.insert(0, f'同为「{same}」')
        if kind in ('main', 'extra'):
            score += 0.05 * (c.frame == base.frame) + 0.04 * (c.attribute == base.attribute) \
                + 0.04 * (abs(c.level - base.level) <= 1)
        elif c.level == base.level:                      # spell/trap subtype code (e.g. counter traps)
            score += 0.05
        theirs_hit = _hits(c) if hits else set()
        off_target = theirs_hit and not hits & theirs_hit or hits and not narrow and _narrow(c)
        if theirs_hit and not hits & theirs_hit:
            score -= 0.2
        if hits and not narrow and _narrow(c):
            score -= 0.1
        # Staples proven in real decks come first when they do the same job (闪电旋涡 over 封魔一闪,
        # 贪欲之壶 for 强欲之壶): a shared role, or close text, and the base's archetype if it has one.
        tier = n in staples and not off_target and (same or not arch) and \
            (shared and len(shared) * 2 >= len(roles | theirs) or text >= 0.35)
        if tier:
            reasons.insert(0, tags.TAGS['staple'])
        # Swaps keep the deck's Tuner count: a Tuner for a Tuner (Dark Tuner for Dark Tuner), a
        # non-Tuner for a non-Tuner. Other cards still come after them, as a fallback.
        other_kind = kind == 'main' and c.tuner != base.tuner
        if base.tuner and not other_kind:
            reasons.append(tags.TAGS['tuner'])
        out.append((n, round(score, 3), reasons or ['效果文字相近'], tier, other_kind, bool(same)))
    out.sort(key=lambda x: (x[4], not x[3], -x[1]))
    seen, keep, cross = set(), [], []
    for n, score, reasons, _, other_kind, same in out:  # TFSP lists some cards under two numbers
        if cards[n].name not in seen:
            seen.add(cards[n].name)
            keep.append((n, score, reasons))
            if other_kind and same:
                cross.append((n, score, reasons))
    # 六武众的影武者 is the archetype's only Tuner in TF6: list Tuners first, but keep the best two
    # 六武众 non-Tuners at the end, so the player chooses between the synchro count and the archetype.
    cross = [o for o in cross[:2] if o not in keep[:limit]]
    return keep[:limit - len(cross)] + cross


def align(deck, cards, cap, ok=None, limit=6):
    """Fit a deck built under another ban list to this game's copy caps.
    `deck` = {'main', 'extra', 'side': [numbers]}; `cap(n)` → copies allowed in main+extra (the side
    deck does not count); `ok(n)` → whether n may be added at all. Returns (fitted deck, cuts) where
    cuts = [(num, section, copies lost, options)] and options are similar() results that still have room."""
    fitted, used, lost = {'side': list(deck.get('side', ()))}, Counter(), Counter()
    for sec in ('main', 'extra'):
        fitted[sec] = []
        for n in deck.get(sec, ()):
            if used[n] < cap(n):
                fitted[sec].append(n)
                used[n] += 1
            else:
                lost[(n, sec)] += 1

    def room(n):
        return cap(n) - used[n] if ok is None or ok(n) else 0

    cuts = [(n, sec, k, similar(n, cards, room, limit)) for (n, sec), k in lost.items()]
    return fitted, cuts


def suggest(cuts, cap, used):
    """Default swap per cut: the best option that still has room once earlier picks are counted.
    `used` = Counter of copies already in the fitted main+extra. Returns {(num, section): card or 0}."""
    taken = Counter(used)
    picks = {}
    for n, sec, lost, options in cuts:
        pick = next((o for o, _, _ in options if cap(o) - taken[o] > 0), 0)
        if pick:
            taken[pick] += min(lost, cap(pick) - taken[pick])
        picks[(n, sec)] = pick
    return picks


def fill(fitted, cuts, picks, cap):
    """Deck with the picked swaps added (each takes as many of the lost copies as its cap allows)."""
    out = {s: list(v) for s, v in fitted.items()}
    taken = Counter(out['main'] + out['extra'])
    for n, sec, lost, _ in cuts:
        pick = picks.get((n, sec))
        if pick:
            k = max(0, min(lost, cap(pick) - taken[pick]))
            out[sec] += [pick] * k
            taken[pick] += k
    return out
