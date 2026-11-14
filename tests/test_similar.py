from collections import Counter

from tfcore import importer, similar, tags
from tfcore.cardsource import CardSource

REBORN, CHARITY, RAIGEKI, DARK_HOLE, MIRROR_FORCE, VEILER, SHADOW = 4842, 4812, 4343, 4342, 4887, 8933, 9316
SPEAR = 6963                                       # 六武众－枪左


def _names(db, num, room=lambda n: 3):
    return [db.cards[n].name for n, _, _ in similar.similar(num, db.cards, room)]


def test_same_kind_and_role(tf6_db):
    top = similar.similar(MIRROR_FORCE, tf6_db.cards, lambda n: 3)
    assert all(tf6_db.cards[n].attribute == 'TRAP' for n, _, _ in top)
    assert '攻击反应坑' in top[0][2]
    assert DARK_HOLE in [n for n, _, _ in similar.similar(RAIGEKI, tf6_db.cards, lambda n: 3)[:2]]
    assert all('手坑' in why or '无效' in why for _, _, why in similar.similar(VEILER, tf6_db.cards, lambda n: 3)[:4])


def test_old_wording_wipes(tf6_db):
    HARPIE, VORTEX, FISH_ONLY = 4678, 5217, 4670
    assert 'wipe' in tags.from_text(tf6_db.cards[RAIGEKI])        # 「对方场上存在的全部怪兽破坏」
    top = [n for n, _, _ in similar.similar(RAIGEKI, tf6_db.cards, lambda n: 3)]
    assert top[:2] == [DARK_HOLE, VORTEX]                          # staple first
    assert HARPIE not in top and FISH_ONLY not in top              # not spells/traps, not one type only
    assert [n for n, _, _ in similar.similar(DARK_HOLE, tf6_db.cards, lambda n: 3)][:2] == [RAIGEKI, VORTEX]


def test_staples_doing_the_same_job_first(tf6_db):
    POT, GREED, SANGAN, WITCH = 4844, 6511, 4054, 4580
    cards = tf6_db.cards
    top = similar.similar(POT, cards, lambda n: 3)
    assert top[0][0] == GREED and top[0][2][0] == '通用强卡'
    sangan = [n for n, _, _ in similar.similar(SANGAN, cards, lambda n: 3)]
    assert sangan[0] == WITCH                                    # not 雷王 (only mentions searching)
    assert all('六武众' in name for name in _names(tf6_db, SPEAR)[:3])    # archetype beats staples


def test_tuner_for_tuner(tf6_db):
    JUNK_SYNCHRON, ZOMBIE_CARRIER = 7687, 7849
    cards = tf6_db.cards
    assert 'tuner' in tags.from_text(cards[JUNK_SYNCHRON])
    for base in (JUNK_SYNCHRON, ZOMBIE_CARRIER):
        top = similar.similar(base, cards, lambda n: 3)
        assert all(cards[n].tuner == 1 for n, _, _ in top[:4])
        # only same-archetype cards may follow as non-Tuner alternatives (同调士探索者 for 废品同调士)
        assert all(cards[n].tuner == 1 or '同为' in why[0] for n, _, why in top)
    dark = next(n for n, c in cards.items() if c.tuner == 2 and c.is_monster)
    assert all(cards[n].tuner == 2 for n, _, _ in similar.similar(dark, cards, lambda n: 3)[:4])
    assert all(cards[n].tuner == 0 for n, _, _ in similar.similar(SPEAR, cards, lambda n: 3)[:4])


def test_tuner_or_archetype(tf6_db):
    # 六武众的影武者 is the only 六武众 Tuner: Tuners first, then the best 六武众 non-Tuners to choose from
    cards = tf6_db.cards
    top = similar.similar(SHADOW, cards, lambda n: 3)
    assert cards[top[0][0]].tuner == 1 and '调整' in top[0][2]
    tail = [cards[n] for n, _, _ in top[-2:]]
    assert all('六武众' in c.name and not c.tuner for c in tail)


def test_archetype_first(tf6_db):
    assert all('六武众' in name for name in _names(tf6_db, SPEAR)[:3])


def test_room_filters(tf6_db):
    banned = {n for n, _, _ in similar.similar(CHARITY, tf6_db.cards, lambda n: 3)}
    rest = similar.similar(CHARITY, tf6_db.cards, lambda n: 0 if n in banned else 3)
    assert rest and not banned & {n for n, _, _ in rest}
    assert similar.similar(999999, tf6_db.cards, lambda n: 3) == []


def test_align_trims_and_suggests(tf6_db):
    cap = lambda n: {REBORN: 1, RAIGEKI: 0}.get(n, 3)
    deck = {'main': [REBORN] * 3 + [RAIGEKI] + [CHARITY] * 2, 'extra': [], 'side': [RAIGEKI]}
    fitted, cuts = similar.align(deck, tf6_db.cards, cap)
    assert Counter(fitted['main']) == {REBORN: 1, CHARITY: 2} and fitted['side'] == [RAIGEKI]
    assert {(n, sec, k) for n, sec, k, _ in cuts} == {(REBORN, 'main', 2), (RAIGEKI, 'main', 1)}
    assert all(o not in (REBORN, RAIGEKI) for _, _, _, opts in cuts for o, _, _ in opts)
    picks = similar.suggest(cuts, cap, Counter(fitted['main']))
    assert picks[(RAIGEKI, 'main')] == cuts[[c[0] for c in cuts].index(RAIGEKI)][3][0][0]
    out = similar.fill(fitted, cuts, picks, cap)
    assert len(out['main']) == 6 and Counter(out['main'])[REBORN] == 1
    out = similar.fill(fitted, cuts, {**picks, (REBORN, 'main'): 0}, cap)
    assert len(out['main']) == 4                      # 0 = just drop the copies


def test_align_respects_ok_and_shared_room(tf6_db):
    cap = lambda n: 0 if n == DARK_HOLE else 3
    _, cuts = similar.align({'main': [DARK_HOLE] * 3}, tf6_db.cards, cap, ok=lambda n: n != RAIGEKI)
    assert RAIGEKI not in [o for o, _, _ in cuts[0][3]]
    one = {'main': [DARK_HOLE], 'extra': [], 'side': []}
    fitted, cuts = similar.align(one, tf6_db.cards, lambda n: 0 if n == DARK_HOLE else 1)
    pick = similar.suggest(cuts, lambda n: 1, Counter())[(DARK_HOLE, 'main')]
    assert similar.fill(fitted, cuts, {(DARK_HOLE, 'main'): pick}, lambda n: 1)['main'] == [pick]


def test_importer_reports_cuts(tf6_db):
    src = CardSource('iso', 'test', tf6_db.cards)
    r = importer.run('死者苏生*3\n黑洞*2', src, trunk=lambda n: (9, 1) if n == REBORN else (9, 3))
    assert r.cuts == [(REBORN, 'main', 2, '限制 1 张')] and Counter(r.main)[REBORN] == 1
