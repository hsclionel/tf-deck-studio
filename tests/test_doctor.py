import pytest

from tfcore import doctor, importer
from tfcore.cardsource import CardSource
from tfcore.tf6save import Deck
from conftest import ROOT


def test_hypergeometric_known_values():
    assert doctor.p_at_least(40, 3, 5) == pytest.approx(0.3376, abs=1e-4)      # classic 3-of in 40, 5 cards
    assert doctor.p_at_least(40, 1, 5) == pytest.approx(5 / 40)
    assert doctor.p_at_least(40, 0, 5) == 0.0
    assert doctor.p_at_least(40, 3, 40) == 1.0
    assert doctor.p_at_least(40, 3, 5, k=2) == pytest.approx(0.0364, abs=1e-4)


def test_cards_seen():
    assert doctor.cards_seen(1, True) == 5 and doctor.cards_seen(1, False) == 6
    assert doctor.cards_seen(3, True) == 7


def test_tuners_decoded(tf6_db):
    assert tf6_db.cards[7687].tuner == 1                                    # 废品同调士
    assert tf6_db.cards[7734].tuner == 0                                    # Stardust Dragon
    assert tf6_db.cards[3605].tuner == 2                                    # ＤＴ灾祸


def test_analyse_fate_deck(tf6_db):
    src = CardSource('iso', 't', tf6_db.cards)
    res = importer.run((ROOT / 'tests' / 'data' / 'import_fate.txt').read_text(encoding='utf-8'), src)
    r = doctor.analyse(Deck('x', res.main, res.extra), tf6_db.cards)
    assert r.main == 40 and r.monsters + r.spells + r.traps == 40
    assert r.extra_by_frame.get('darksynchro') == 4
    texts = ' '.join(t for _, t in r.advice)
    assert '黑暗调整' in texts                         # Dark Synchros but no ＤＴ in the main deck
    o = doctor.odds(res.main, [8301])                  # 命运女郎·莱蒂 ×3
    assert o['先攻起手'] == pytest.approx(doctor.p_at_least(40, 3, 5))


def test_xyz_rank_advice(tf6_db):
    utopia = 9575                                      # No.39 希望皇 霍普, rank 4
    fillers = [n for n, c in tf6_db.cards.items() if c.is_monster and c.level == 8 and not c.extra_deck][:13]
    spells = [n for n, c in tf6_db.cards.items() if c.attribute == 'SPELL'][:27]
    r = doctor.analyse(Deck('x', fillers + spells, [utopia]), tf6_db.cards)
    assert any('4 阶超量' in t for _, t in r.advice)
