"""Issue #2: the card browser matches effect text too, without burying the name matches."""
from tfcore import textsearch


def test_name_hits_rank_above_text_hits():
    q = textsearch.normalize('战士族')
    name = textsearch.normalize('战士族的骄傲')
    text = textsearch.normalize('从卡组把1只4星以下的战士族怪兽加入手卡。')
    assert textsearch.hit(q, textsearch.normalize('增援'), text) == textsearch.TEXT_HIT
    assert textsearch.hit(q, name, '……') == textsearch.NAME_HIT
    assert textsearch.rank(q, name, '……') < textsearch.rank(q, textsearch.normalize('增援'), text)
    assert textsearch.rank(q, textsearch.normalize('增援'), text) < textsearch.rank(q, textsearch.normalize('青眼白龙'), '……')


def test_no_hit_anywhere():
    q = textsearch.normalize('xyz')
    assert textsearch.hit(q, textsearch.normalize('青眼白龙'), textsearch.normalize('这张卡不能通常召唤。')) == textsearch.NO_HIT
    assert textsearch.hit('', '青眼白龙', '字段') == textsearch.NO_HIT       # empty query filters nothing


def test_numbers_count_as_name_hits():
    numbers = ('8963', '89631139')
    assert textsearch.hit('8963', '青眼白龙', '……', numbers) == textsearch.NAME_HIT
    assert textsearch.hit('3113', '青眼白龙', '……', numbers) == textsearch.NAME_HIT   # partial passcode still finds it
    assert textsearch.hit('4975', '青眼白龙', '攻击力 3000', numbers) == textsearch.NO_HIT
    assert textsearch.hit('one', '青眼白龙', '……', (None, None)) == textsearch.NO_HIT   # no passcode, no match


def test_punctuation_and_width_do_not_matter():
    assert textsearch.normalize('Ｅ·ＨＥＲＯ　天空侠') == 'ehero天空侠'
    q = textsearch.normalize('抽 1 张卡')
    assert textsearch.hit(q, '强欲之壶', textsearch.normalize('从卡组抽1张卡。')) == textsearch.TEXT_HIT
    assert textsearch.hit(textsearch.normalize('抽1张卡'), '强欲之壶', textsearch.normalize('从卡组抽１张卡。')) == textsearch.TEXT_HIT
