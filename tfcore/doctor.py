"""Deck analysis: composition, opening-hand odds and rule-of-thumb advice.

Odds are exact hypergeometric probabilities. Tag Force deals 5 cards and, as in the 2011 rules,
the player going first skips the draw on turn 1; so by your n-th turn you have seen
5 + (n - 1) cards going first and 5 + n going second.

Advice is a handful of transparent heuristics, each saying why; they are suggestions, not rules.
"""
from collections import Counter
from dataclasses import dataclass, field
from math import comb

HAND = 5


def p_at_least(deck_size, copies, seen, k=1):
    """P(at least k of `copies` cards among `seen` cards drawn from `deck_size`)."""
    if copies <= 0 or seen <= 0:
        return 0.0
    seen = min(seen, deck_size)
    total = comb(deck_size, seen)
    hit = sum(comb(copies, i) * comb(deck_size - copies, seen - i) for i in range(k, min(copies, seen) + 1))
    return hit / total


def cards_seen(turn, first):
    """Cards seen by your `turn`-th turn (1-based)."""
    return HAND + (turn - 1 if first else turn)


DRAWS = (('先攻起手', 1, True), ('后攻起手', 1, False), ('先攻第2回合', 2, True), ('先攻第3回合', 3, True))


def odds(main, group, draws=DRAWS):
    """{label: P(≥1 card of `group`)} for the main deck `main` (list of card numbers)."""
    group = set(group)
    copies = sum(1 for n in main if n in group)
    return {label: p_at_least(len(main), copies, cards_seen(turn, first)) for label, turn, first in draws}


@dataclass
class Report:
    main: int = 0
    monsters: int = 0
    spells: int = 0
    traps: int = 0
    unknown: int = 0                                  # cards without type data (save-only, no names)
    by_frame: dict = field(default_factory=dict)      # main-deck monsters by frame
    levels: dict = field(default_factory=dict)        # main-deck monsters by level
    extra_by_frame: dict = field(default_factory=dict)
    tuners: int = 0
    dark_tuners: int = 0
    copies: dict = field(default_factory=dict)        # card → copies in main
    advice: list = field(default_factory=list)        # (level 'warn'|'info'|'good', text)


def analyse(deck, cards):
    """Report for a Deck (main/extra/side lists of card numbers); `cards` maps num → Card."""
    r = Report()
    main = [n for n in deck.main if n in cards]
    r.main = len(deck.main)
    r.unknown = r.main - len(main)
    r.copies = dict(Counter(main))
    frames, levels = Counter(), Counter()
    for n in main:
        c = cards[n]
        if c.attribute == '?':
            r.unknown += 1
        elif c.attribute == 'SPELL':
            r.spells += 1
        elif c.attribute == 'TRAP':
            r.traps += 1
        else:
            r.monsters += 1
            frames[c.frame] += 1
            if c.level:
                levels[c.level] += 1
            r.tuners += c.tuner == 1
            r.dark_tuners += c.tuner == 2
    r.by_frame, r.levels = dict(frames), dict(sorted(levels.items()))
    r.extra_by_frame = dict(Counter(cards[n].frame for n in deck.extra if n in cards))
    r.advice = _advice(r, deck, cards)
    return r


def _advice(r, deck, cards):
    out = []
    if r.main > 40:
        p40, pn = p_at_least(40, 3, HAND), p_at_least(r.main, 3, HAND)
        out.append(('info', f'主卡组有 {r.main} 张。越接近 40 张，关键卡越容易上手：'
                            f'放 3 张的卡，先攻起手抽到的概率 40 张时是 {p40:.0%}，现在是 {pn:.0%}。'))
    if r.unknown:
        out.append(('info', f'{r.unknown} 张卡缺少类型资料，下面的统计不完整。加上游戏 ISO 或下载卡名库后会更准。'))
        return out
    if r.main and r.monsters < 12:
        out.append(('warn', f'怪兽只有 {r.monsters} 张，常会没怪兽可出。一般放 13–20 张比较稳。'))
    elif r.monsters > 26:
        out.append(('info', f'怪兽有 {r.monsters} 张，魔法陷阱只有 {r.spells + r.traps} 张，应对手段可能不够。'))
    if r.main and r.traps == 0:
        out.append(('info', '没有陷阱卡，对手回合基本没法干扰。'))

    synchros = sum(v for k, v in r.extra_by_frame.items() if k == 'synchro')
    if synchros and r.tuners == 0:
        out.append(('warn', f'额外卡组有 {synchros} 张同调怪兽，主卡组却没有调整，没法同调召唤。'))
    elif synchros >= 3 and r.tuners < 3:
        out.append(('info', f'同调怪兽有 {synchros} 张，调整只有 {r.tuners} 张，能同调的机会可能偏少。'))
    if r.extra_by_frame.get('darksynchro') and r.dark_tuners == 0:
        out.append(('warn', '额外卡组有黑暗同调怪兽，主卡组却没有黑暗调整（ＤＴ）。'))

    ranks = Counter(cards[n].level for n in deck.extra if n in cards and cards[n].frame == 'xyz')
    for rank in sorted(ranks):
        same = r.levels.get(rank, 0)
        if same < 6:
            out.append(('warn' if same < 3 else 'info',
                        f'额外卡组有 {ranks[rank]} 张 {rank} 阶超量怪兽，主卡组的 {rank} 星怪兽却只有 {same} 张。'))

    if r.extra_by_frame.get('fusion') and not any(
            cards[n].attribute == 'SPELL' and ('融合' in cards[n].name or '融合召唤' in cards[n].text)
            for n in deck.main if n in cards):
        out.append(('info', '额外卡组有融合怪兽，主卡组里却没看到能融合召唤的魔法卡（也可能另有召唤方法）。'))
    if r.by_frame.get('ritual') and not any(
            cards[n].attribute == 'SPELL' and '仪式' in cards[n].name for n in deck.main if n in cards):
        out.append(('warn', '有仪式怪兽，但没有仪式魔法卡。'))

    high = sum(v for lv, v in r.levels.items() if lv >= 7)
    if high >= 5:
        out.append(('info', f'7 星以上的怪兽有 {high} 张，要 2 只祭品或特殊召唤才能出，容易卡手。'))
    singles = sum(1 for k in r.copies.values() if k == 1)
    if singles >= 12:
        out.append(('info', f'有 {singles} 种卡只放了 1 张，每局抽到什么比较看运气。'))
    if not out:
        out.append(('good', '没看出明显的结构问题。'))
    return out
