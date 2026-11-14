import os
from collections import Counter

import pytest

from tfcore import recipes
from conftest import TF6_ISO, TFSP_ISO


@pytest.fixture(scope='module')
def tfsp_recipes():
    if not os.path.exists(TFSP_ISO):
        pytest.skip('TFSP ISO not found')
    return recipes.from_iso(TFSP_ISO)


def test_tfsp_recipes(tfsp_recipes, tfsp_db):
    r = tfsp_recipes
    assert len(r) == 841 and [x.index for x in r] == list(range(841))
    cats = Counter(x.category for x in r)
    assert cats['character'] == 768 and cats['wcs'] == 6 and cats['meta'] == 6 and cats['starter0'] == 3
    assert all(n in tfsp_db.cards for x in r for n in x.main + x.extra + x.side)
    assert all(40 <= len(x.main) <= 60 and len(x.extra) <= 15 and len(x.side) <= 15 for x in r)
    yusei = [x for x in r if x.character == '不动 游星']
    assert [x.level for x in yusei] == [1, 2, 3, 4] and yusei[3].name == '限制超越・星尘'
    assert tfsp_db.name_of(7687) and 7687 in yusei[3].main                   # 废品同调士
    wcs09 = r[777]
    assert wcs09.name.startswith('ＷＣＳ２００９') and wcs09.champion and len(wcs09.side) == 15
    assert sum(x.champion for x in r) == 192 + 18


def test_round_trip(tfsp_recipes, tmp_path):
    path = tmp_path / 'recipes.json'
    recipes.save(tfsp_recipes, path)
    assert recipes.load(path) == tfsp_recipes


def test_encrypted_eboot_gives_nothing():
    if not os.path.exists(TF6_ISO):
        pytest.skip('TF6 ISO not found')
    assert recipes.from_iso(TF6_ISO) == []
    assert recipes.extract(b'~PSP' + bytes(100)) == []
