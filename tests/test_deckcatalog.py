import json, os
from types import SimpleNamespace

import pytest

from tfcore import deckcatalog, recipes, wikidecks

PAGE = """== Decks ==
=== Tag Force 6 ===
{{Decklist
| name = Test Deck
| ja_name = テスト
| level = 9
| effect monsters =
* [[Junk Synchron]] x3
* [[Not A Real Card]]
| synchro monsters =
* [[Stardust Dragon]]
}}
"""
NAMES = {7687: {'cid': 7687, 'en_name': 'Junk Synchron'}, 7734: {'cid': 7734, 'en_name': 'Stardust Dragon'}}


def test_from_recipes():
    r = [recipes.Recipe(5, 'A', 'character', 'Yusei', 4, [1, 2], [3], []),
         recipes.Recipe(800, 'B', 'structure', main=[4])]
    a, b = deckcatalog.from_recipes(r)
    assert (a.key, a.group, a.champion, a.level_label) == ('rcp:5', '角色卡组', True, 'Lv4')
    assert (b.group, b.champion, b.level_label) == ('构筑预组', False, '')


def test_wiki_store(tmp_path):
    store = deckcatalog.WikiStore(str(tmp_path))
    assert store.supported('TF6') and not store.supported('TFSP') and not store.has('TF6')
    os.makedirs(store.folder)
    with open(store.path('TF6'), 'w', encoding='utf-8') as f:
        json.dump({'Yusei Fudo (Tag Force)': PAGE}, f)
    cards = {7687: object(), 7734: object()}
    assert store.decks('TF6', cards, None) == []                  # needs English names
    [e] = deckcatalog.from_wiki(store.decks('TF6', cards, NAMES))
    assert (e.name, e.character, e.level_label, e.champion) == ('テスト', 'Yusei Fudo', '9★', True)
    assert e.main == [7687] * 3 and e.extra == [7734] and e.missing == ['Not A Real Card']
    assert e.source == wikidecks.SOURCE and e.url.endswith('Yusei_Fudo_%28Tag_Force%29')
    src = SimpleNamespace(catalog=None, cards=cards)
    assert [x.key for x in deckcatalog.entries(src, 'TF6', store, NAMES)] == [e.key]


def test_tfsp_entries(tfsp_db):
    from conftest import TFSP_ISO
    if not os.path.exists(TFSP_ISO):
        pytest.skip('TFSP ISO not found')
    cat = SimpleNamespace(game='TFSP', recipes=lambda: recipes.from_iso(TFSP_ISO))
    src = SimpleNamespace(catalog=cat, cards=tfsp_db.cards)
    found = deckcatalog.entries(src, 'TFSP', deckcatalog.WikiStore('nowhere'), None)
    assert len(found) == 841 and sum(e.champion for e in found) == 210
