import json, os, shutil

import pytest

from conftest import MEMSTICK, TF6_ISO
from tfcore.cardsource import GAME_ONLY
from tfcore.tf6save import Deck
from tfcore.workspace import Workspace

FAKE_NAMES = {'a': {'cid': 4007, 'id': 89631139, 'cn_name': '青眼白龙', 'en_name': 'Blue-Eyes White Dragon',
                    'text': {'desc': 'x'}, 'data': {'type': 17, 'attribute': 16, 'level': 8, 'atk': 3000, 'def': 2500}},
              'b': {'cid': 6784, 'id': 40044918, 'cn_name': '元素英雄 天空侠', 'en_name': 'Elemental HERO Stratos',
                    'text': {'desc': 'y'}, 'data': {'type': 33, 'attribute': 8, 'level': 4, 'atk': 1800, 'def': 300}},
              'c': {'cid': 4844, 'id': 55144522, 'cn_name': '强欲之壶', 'data': {'type': 2}}}


@pytest.fixture
def ws(tmp_path):
    return Workspace(str(tmp_path / 'home'))


@pytest.fixture
def memstick(tmp_path):
    root = tmp_path / 'ms' / 'PSP' / 'SAVEDATA'
    shutil.copytree(MEMSTICK, root)
    return tmp_path / 'ms'


def with_names(ws):
    os.makedirs(os.path.dirname(ws.names_path), exist_ok=True)
    json.dump(FAKE_NAMES, open(ws.names_path, 'w', encoding='utf-8'), ensure_ascii=False)


def test_find_saves(memstick):
    found = Workspace.find_saves(str(memstick))
    assert [os.path.basename(p) for p in found] == ['NPJH001420001', 'ULJM059400001']
    assert Workspace.find_saves(found[1]) == [found[1]]


def test_numbers_only_without_any_data(ws, memstick):
    s = ws.open_save(Workspace.find_saves(str(memstick))[1])
    src = s.source
    assert src.kind == 'numbers' and not src.has_art and len(src.cards) == 5392   # built-in TF6 pool
    assert src.can_add(4007) and not src.can_add(4006)                             # 4006 is not in TF6
    assert src.cards[3459].name == '时械天使' and src.cards[3459].game_only          # built-in game card
    assert s.trunk(6784) == (9, 1)                                                 # owned 9, ban list 1
    assert ws.config['recent_saves'][0].endswith('ULJM059400001')


def test_names_only_source(ws, memstick):
    with_names(ws)
    s = ws.open_save(Workspace.find_saves(str(memstick))[1])
    src = s.source
    assert src.kind == 'names' and len(src.cards) == 5392
    assert src.cards[6784].name == '元素英雄 天空侠' and src.alt_names[6784]['en'] == 'Elemental HERO Stratos'
    assert src.cards[4844].frame == 'spell' and src.cards[4007].frame == 'normal'
    assert src.cards[6310].name == '#6310' and src.cards[6310].text == GAME_ONLY     # not in the fake db
    assert src.cards[3459].name == '时械天使'                                        # built-in game card
    assert s.trunk(6784) == (9, 1)
    deck = Deck('x', [6784] * 2 + list(range(5000, 5038)))
    msgs = ' '.join(s.problems(deck))
    assert '元素英雄 天空侠 ×2, limit 1' in msgs
    assert s.banlist
    s.set_banlist(False)                                # the player turned the ban list off in the game
    assert s.trunk(6784) == (9, 3) and '天空侠' not in ' '.join(s.problems(deck))
    assert ws.config['banlist'] == {'TF6': False}
    assert ws.open_save(Workspace.find_saves(str(memstick))[1]).banlist is False   # remembered per game
    s.set_banlist(True)
    assert s.trunk(6784) == (9, 1)


def test_tfsp_save_opens_for_editing(ws, memstick):
    s = ws.open_save(Workspace.find_saves(str(memstick))[0])
    assert not s.read_only and s.source.has_trunk and len(s.source.cards) == 7254
    assert s.save.decks() == {}                       # this save predates any deck edit in-game


def test_iso_source_and_commit(ws, memstick):
    if not os.path.exists(TF6_ISO):
        pytest.skip('no TF6 ISO')
    cat = ws.add_iso(TF6_ISO)
    assert [c.game for c in ws.catalogs()] == ['TF6'] and cat.language == 'zh' and cat.pool_ok
    s = ws.open_save(Workspace.find_saves(str(memstick))[1])
    assert s.source.kind == 'iso' and s.source.has_art and s.trunk(6784) == (9, 1)
    d = s.save.deck(3)
    backup = s.commit({3: Deck('元素英雄改', d.main, d.extra, d.side)})
    assert os.path.isdir(backup)
    again = ws.open_save(s.folder.path)
    assert again.save.deck(3).name == '元素英雄改'
