import os

import pytest

from conftest import ROOT
from tfcore import gamecards, pools, ygocdb

NAMES = ROOT / 'testdata' / 'apphome' / 'ygocdb' / 'cards.json'
# The built-in files hold text from the game, so they are not in the public repository; generate
# them from your ISO with `python -m tfcore.cli pool <iso> [--names cards.json]`.
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(gamecards.DIR, 'TF6.json')),
                                reason='built-in game cards not generated')


def test_builtin_game_cards():
    tf6, sp = gamecards.load('TF6'), gamecards.load('TFSP')
    assert len(tf6) == 352 and len(sp) == 456
    t = tf6[3459]
    assert (t.name, t.attribute, t.frame, t.game_only) == ('时械天使', 'LIGHT', 'effect', True)
    assert t.text and all(n in pools.load('TF6') for n in tf6)
    assert not any('$m' in c.text for c in tf6.values() if c.num != 3728)


def test_matches_iso(tf6_db):
    for n, c in gamecards.load('TF6').items():
        rom = tf6_db.cards[n]
        assert (c.name, c.text, c.attribute, c.frame, c.level, c.atk, c.defense) == \
               (rom.name, rom.text, rom.attribute, rom.frame, rom.level, rom.atk, rom.defense)


@pytest.mark.skipif(not os.path.exists(NAMES), reason='no ygocdb snapshot')
def test_every_card_is_described_without_iso():
    names = ygocdb.load(NAMES)
    for game in ('TF6', 'TFSP'):
        builtin = gamecards.load(game)
        missing = [n for n in pools.load(game).nums if n not in builtin and n not in names]
        assert missing == [], f'{game}: {missing[:10]}'
