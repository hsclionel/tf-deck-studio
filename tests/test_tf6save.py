"""Replays the in-game-verified edit chain with the library and expects identical plaintexts."""
import dataclasses

import pytest

from conftest import CHAIN
from tfcore import savecrypto
from tfcore.games import TAG_FORCE_KEY
from tfcore.tf6save import Deck, TF6Save


def plain(folder):
    return savecrypto.decrypt(5, (folder / 'DATA0').read_bytes(), TAG_FORCE_KEY)


@pytest.fixture
def saves():
    return [TF6Save(plain(f)) for f in CHAIN]


def test_reads_decks(saves):
    decks = saves[0].decks()
    assert [d.name for d in decks.values()] == ['65', 'jd', 'sfby']
    assert [(len(d.main), len(d.extra), len(d.side)) for d in decks.values()] == [(40, 15, 0), (40, 8, 0), (40, 13, 2)]
    assert saves[0].free_slot() == 3


def test_rename_reproduces_step_2(saves):
    s = saves[0]
    for slot, name in ((0, '真六武众'), (1, '剑斗兽')):
        s.write_deck(slot, dataclasses.replace(s.deck(slot), name=name))
    assert s.data == saves[1].data


def test_new_slot_reproduces_step_3(saves):
    target = saves[2].deck(3)
    s = saves[1]
    s.write_deck(3, Deck(target.name, target.main, target.extra, target.side, stamp=target.stamp, tag=target.tag))
    assert s.data == saves[2].data


def test_extra_deck_edit_reproduces_step_4(saves):
    target = saves[3].deck(3)
    s = saves[2]
    s.write_deck(3, Deck('ignored for stamp/tag', target.main, target.extra, target.side))
    s.write_deck(3, dataclasses.replace(target))   # existing slot keeps its stamp and tag
    assert s.data == saves[3].data


def test_new_slot_gets_fresh_tag_and_stamp(saves):
    s = saves[0]
    d = s.deck(0)
    s.write_deck(5, Deck('x', d.main, d.extra))
    new = s.deck(5)
    assert new.tag and new.tag < 1 << 20 and new.tag not in {s.deck(i).tag for i in range(3)}
    assert new.stamp[0] >= 2026


def test_rejects_bad_sizes(saves):
    with pytest.raises(ValueError):
        saves[0].write_deck(5, Deck('short', [4007] * 10))
    with pytest.raises(ValueError):
        saves[0].write_deck(5, Deck('x' * 64, [4007] * 40))


def test_rule_check(saves, tf6_db):
    s = saves[3]
    assert all(not s.problems(d, tf6_db) for d in s.decks().values())
    stratos = 6784                                     # limited to 1 in the save's ban cache
    assert s.trunk(tf6_db.row_of(stratos))[1] == 1
    bad = Deck('bad', [stratos] * 2 + [6313] * 38, extra=[6313])
    msgs = ' '.join(s.problems(bad, tf6_db))
    assert 'limit 1' in msgs and 'main deck' in msgs
