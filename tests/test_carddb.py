import pathlib, re

from conftest import TF6_ISO
from tfcore import art, iso
from tfcore.games import CARD_ART_PATH


def test_tf6_spot_checks(tf6_db):
    bewd = tf6_db.cards[4007]
    assert (bewd.row, bewd.passcode, bewd.name) == (312, 89631139, '青眼白龙')
    assert (bewd.attribute, bewd.frame, bewd.level, bewd.atk, bewd.defense) == ('LIGHT', 'normal', 8, 3000, 2500)
    assert tf6_db.cards[4844].passcode == 55144522 and tf6_db.cards[4844].frame == 'spell'
    assert tf6_db.cards[4887].frame == 'trap'
    stardust = tf6_db.cards[7734]
    assert (stardust.passcode, stardust.attribute, stardust.frame, stardust.level) == (44508094, 'WIND', 'synchro', 8)
    assert tf6_db.cards[6467].frame == 'fusion' and tf6_db.cards[6467].extra_deck
    assert tf6_db.cards[9311].frame == 'effect'
    assert tf6_db.row_of(4007) == 312 and tf6_db.row_of(3459 + 100000) == 0
    assert len(tf6_db.cards) == 5392


def test_tf6_texts(tf6_db):
    assert '「ＨＥＲＯ」' in tf6_db.cards[9066].text
    assert '「虚无械眼」' in tf6_db.cards[3471].text            # $m3470 resolved
    unresolved = [c.num for c in tf6_db.cards.values() if re.search(r'\$m\d', c.text)]
    assert unresolved == [3728]                                # patch typo "$m40641", left visible
    assert sum(not c.text for c in tf6_db.cards.values()) < 5


def test_tfsp_shifted_layout(tfsp_db):
    c = tfsp_db.cards
    assert (c[4007].attribute, c[4007].level, c[4007].frame) == ('LIGHT', 8, 'normal')
    assert (c[7734].attribute, c[7734].level, c[7734].frame) == ('WIND', 8, 'synchro')
    assert c[4844].attribute == 'SPELL' and c[4887].attribute == 'TRAP'
    assert c[9575].frame == 'xyz' and c[11213].frame == 'pendulum'
    assert len(c) == 7254 and max(c) == 11657


def test_card_art(tf6_db):
    cardh = iso.fetch(iso.open_iso(TF6_ISO), CARD_ART_PATH)
    table = art.cip_index(cardh)
    assert len(table[4007]) == 5 and len(table[6310]) == 2 and len(table[9067]) == 1
    num, k, img = next(art.iter_artworks(cardh))
    assert num == 3459 and img.size == (79, 79)


def test_stats_packed_in_tens(tf6_db, tfsp_db):
    """ATK/DEF are 9-bit values in tens across both stat bytes and the number word; 511 = '?'."""
    for db in (tf6_db, tfsp_db):
        assert (db.cards[4017].atk, db.cards[4017].defense) == (1750, 2030)     # 剑龙: the low digits matter
        assert (db.cards[4069].atk, db.cards[4069].defense) == (1950, 2100)     # 鹰身女郎三姐妹
        assert (db.cards[8089].atk, db.cards[8089].defense) == (-1, -1)         # 特拉戈迪亚 ?/?


def test_monster_types(tf6_db, tfsp_db):
    """f2 holds the monster type; it agrees with ygocdb's race for every monster ygocdb lists."""
    for db in (tf6_db, tfsp_db):
        assert db.cards[4007].race == '龙' and db.cards[7734].race == '龙'          # 青眼白龙, 星尘龙
        assert db.cards[4069].race == '鸟兽' and db.cards[4844].race == ''          # 鹰身女郎三姐妹; a spell
    assert tfsp_db.cards[9575].race                                                 # an Xyz monster
    names = pathlib.Path(__file__).resolve().parent.parent / 'testdata' / 'apphome' / 'ygocdb' / 'cards.json'
    if names.exists():
        from tfcore import ygocdb
        ref = ygocdb.load(names)
        for db in (tf6_db, tfsp_db):
            pairs = [(c.race, ygocdb.RACE.get(ref[n]['data']['race'])) for n, c in db.cards.items()
                     if c.is_monster and 'data' in ref.get(n, {}) and c.frame != 'token']
            assert len(pairs) > 3000 and all(a == b for a, b in pairs)
