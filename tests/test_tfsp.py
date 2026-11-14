"""TFSP save layout, mapped 2026-10-28: the user renamed the starter deck to '111' in PPSSPP."""
import os, shutil

import pytest

from conftest import ROOT
from tfcore import pools, ygocdb
from tfcore.games import GAMES
from tfcore.savefolder import SaveFolder
from tfcore.tf6save import Deck, TF6Save

MAP = ROOT / 'testdata' / 'tfsp_map'
TFSP = GAMES['NPJH00142']
NAMES = ROOT / 'testdata' / 'apphome' / 'ygocdb' / 'cards.json'


def save(step):
    return TF6Save(SaveFolder(MAP / step).plain, TFSP)


def test_rename_put_the_deck_in_slot_0():
    before, after = save('step0_start'), save('step1_rename111')
    assert before.decks() == {}
    d = after.deck(0)
    assert (d.name, len(d.main), len(d.extra), len(d.side)) == ('111', 40, 6, 3)
    assert d.stamp[:3] == (2026, 10, 28)


def test_trunk_offset(tfsp_db):
    s, pool = save('step1_rename111'), pools.load('TFSP')
    tokens = [n for n, c in tfsp_db.cards.items() if c.frame == 'token']
    assert tokens and all(s.trunk(pool.row_of(n))[0] == 0 for n in tokens)
    assert s.trunk(pool.row_of(4844))[1] == 0          # Pot of Greed forbidden
    assert s.trunk(pool.row_of(4842))[1] == 1          # Monster Reborn limited
    assert s.problems(s.deck(0), tfsp_db) == []


def test_write_round_trip(tmp_path):
    folder = tmp_path / 'NPJH001420001'
    shutil.copytree(MAP / 'step1_rename111', folder)
    sf = SaveFolder(folder)
    s = TF6Save(sf.plain, TFSP)
    d = s.deck(0)
    s.write_deck(1, Deck('第二个', d.main, d.extra))
    sf.write(s.data, tmp_path / 'backups')
    again = TF6Save(SaveFolder(folder).plain, TFSP)
    assert again.deck(1).name == '第二个' and again.deck(0).name == '111'


@pytest.mark.skipif(not os.path.exists(NAMES), reason='no ygocdb snapshot')
def test_frames_match_ygocdb(tf6_db, tfsp_db):
    y = ygocdb.load(NAMES)
    for db in (tf6_db, tfsp_db):
        bad = [n for n, c in db.cards.items() if n in y and 'data' in y[n] and c.frame != ygocdb.frame(y[n]['data']['type'])]
        assert bad == []
