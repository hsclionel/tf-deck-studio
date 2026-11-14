import base64, struct

import pytest

from conftest import ROOT
from tfcore import importer
from tfcore.cardsource import CardSource
from tfcore.tf6save import Deck

FATE = (ROOT / 'tests' / 'data' / 'import_fate.txt').read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def src(tf6_db):
    return CardSource('iso', 'TF6 test', tf6_db.cards)


def test_parse_count_formats():
    lines, _ = importer.parse('【怪兽】\nA卡*3\nB卡 x2\nC卡×1\n2 D卡\n3x E卡\nＦ卡＊２\n【额外】\nG卡')
    assert [(ln.text, ln.count, ln.section) for ln in lines] == [
        ('A卡', 3, 'main'), ('B卡', 2, 'main'), ('C卡', 1, 'main'), ('D卡', 2, 'main'),
        ('E卡', 3, 'main'), ('F卡', 2, 'main'), ('G卡', 1, 'extra')]


def test_forum_list_resolves_completely(src):
    res = importer.run(FATE, src)
    assert res.unresolved == []
    assert (len(res.main), len(res.extra), len(res.side)) == (40, 10, 0)
    got = {ln.text: ln.num for ln in res.lines}
    assert got['命运女郎·光'] == 8301 and got['命运女郎·暗'] == 8446      # attribute shorthand
    assert got['咒缚牢'] == src.cards[got['咒缚牢']].num and src.cards[got['咒缚牢']].name == '呪縛牢'
    assert got['罪 星尘龙'] and src.cards[got['罪 星尘龙']].name.startswith('Ｓｉｎ')
    assert got['百眼龙(黑暗同调)'] == 3602 and got['暗黑空母(黑暗同调)'] == 3648   # game Dark Synchro versions
    assert src.cards[3602].frame == 'darksynchro' and src.cards[3602].extra_deck
    assert res.warnings == ['「额外」标的是 15 张，实际列了 10 张']


def test_extra_deck_routing_and_caps(src):
    res = importer.run('【怪兽】\n星尘龙*1\nＥ·ＨＥＲＯ 天空侠*3', src,
                       trunk=lambda n: (9, 1) if n == 6784 else (9, 3))
    assert res.extra == [7734]
    assert res.main == [6784]                                   # Stratos limited to 1 in the save
    assert any('星尘龙' in a for a in res.adjustments)
    assert any('限制 1' in a for a in res.adjustments)


def test_ydk_round_trip(src):
    deck = Deck('x', [4007] * 3 + [4844], [7734], [4887] * 2)
    res = importer.run(importer.to_ydk(deck, src.cards), src)
    assert sorted(res.main) == sorted(deck.main) and res.extra == deck.extra and res.side == deck.side


def test_ydke(src):
    pack = lambda pcs: base64.b64encode(b''.join(struct.pack('<I', p) for p in pcs)).decode()
    url = f'ydke://{pack([89631139, 89631139])}!{pack([44508094])}!{pack([])}!'
    res = importer.run(url, src)
    assert res.main == [4007, 4007] and res.extra == [7734]


def test_unknown_names_stay_unresolved(src):
    res = importer.run('完全不存在的卡片名字*3', src)
    assert len(res.unresolved) == 1 and res.main == []


def test_alias_memory(src):
    res = importer.run('我的自定义名字*1', src, aliases={'我的自定义名字': 4007})
    assert res.main == [4007]


def test_text_export_round_trip(src):
    deck = Deck('x', [8301] * 3 + [4844], [7734] * 2)
    res = importer.run(importer.to_text(deck, src.cards), src)
    assert sorted(res.main) == sorted(deck.main) and res.extra == deck.extra


# ---- real forum lists against both games, with ygocdb names (skipped without the snapshot)

NAMES = ROOT / 'testdata' / 'apphome' / 'ygocdb' / 'cards.json'


@pytest.fixture(scope='module')
def names():
    if not NAMES.exists():
        pytest.skip('no ygocdb snapshot')
    from tfcore import ygocdb
    return ygocdb.load(NAMES)


def _full(db, names):
    from tfcore import ygocdb
    return CardSource('iso', 'test', db.cards, alt_names={n: ygocdb.names(names[n]) for n in db.cards if n in names})


def _run(name, db, names):
    return importer.run((ROOT / 'tests' / 'data' / name).read_text(encoding='utf-8'), _full(db, names), names_db=names)


def test_battery_list(tf6_db, tfsp_db, names):
    sp = _run('import_battery.txt', tfsp_db, names)
    assert sp.unresolved == []
    assert next(ln.num for ln in sp.lines if ln.text == '硬邦邦龙') == 9839   # built-in nickname → 硬梆龙
    assert next(ln.num for ln in sp.lines if ln.text == '反查') == 11180       # Wiretap exists in TFSP
    assert (len(sp.main), len(sp.extra)) == (44, 15)
    assert '「魔法」标的是 14 张，实际列了 12 张' in sp.warnings
    tf6 = _run('import_battery.txt', tf6_db, names)
    wiretap = next(ln for ln in tf6.lines if ln.text == '反查')
    assert wiretap.num == 3643 and tf6.unresolved == []                  # TF6 stand-in: 陷阱封锁
    assert any('陷阱封锁' in a for a in tf6.adjustments)


def test_standins(tf6_db, tfsp_db, names):
    assert importer.standins(tf6_db.cards) == [(11180, 3643, ['反查', 'Wiretap', 'ギャクタン'], 34507039)]
    assert importer.standins(tfsp_db.cards) == []                        # TFSP has the real 反查
    r = importer.run('#main\n34507039\n#extra\n!side\n', _full(tf6_db, names))
    assert [ln.num for ln in r.lines if ln.passcode] == [3643] and tf6_db.cards[3643].name == '陷阱封锁'
    r = importer.run('Wiretap x2', _full(tf6_db, names))                # English name, no ygocdb lookup
    assert r.main == [3643, 3643]


def test_dragunity_list(tf6_db, tfsp_db, names):
    sp = _run('import_dragunity.txt', tfsp_db, names)
    assert sp.unresolved == [] and (len(sp.main), len(sp.extra)) == (40, 15)
    got = {ln.text: tfsp_db.cards[ln.num].name for ln in sp.lines}
    assert got['正义盟军 灾难兽'].startswith('正义盟军')                    # Master Duel name
    assert got['BF-精锐'].startswith('黑羽')                                # BF = 黑羽 in the TFSP patch
    assert got['百眼龙(暗黑同调)'] == '百眼龙' and tfsp_db.cards[next(
        ln.num for ln in sp.lines if ln.text == '百眼龙(暗黑同调)')].game_only
    tf6 = _run('import_dragunity.txt', tf6_db, names)
    assert tf6.unresolved == [] and 3643 in tf6.main                   # 反查 → 陷阱封锁 in TF6


def test_karakuri_list_with_remarks(tf6_db, tfsp_db, names):
    sp = _run('import_karakuri.txt', tfsp_db, names)
    comment = next(ln for ln in sp.lines if ln.comment)
    assert comment.text.startswith('可再带一张机巧无双')                    # a remark, not a card
    assert [ln.text for ln in sp.unresolved] == ['5星机械系融合怪兽']        # a description, left to the user
    general = next(ln for ln in sp.lines if ln.text == '机巧将军 无零怒')
    assert tfsp_db.cards[general.num].name.endswith('无零怒') and '可带2' in general.note
    ninja = next(ln for ln in sp.lines if ln.text == '机巧忍者')
    assert '请确认' in ninja.note and ninja.score < 0.95                     # two Karakuri Ninja
    assert sp.warnings == [] and len(sp.main) == 40


def test_karakuri_list_bracket_star_headers(tf6_db, names):
    res = _run('import_karakuri2.txt', tf6_db, names)          # 【怪兽卡】*16, 【EX卡组】*15 …
    assert res.unresolved == [] and (len(res.main), len(res.extra)) == (40, 15)
    assert next(ln.num for ln in res.lines if ln.text == '汉诺的崇高之力') == 4887   # nickname: Mirror Force
    assert res.adjustments == [] and res.warnings == []
    barkion = next(ln for ln in res.lines if ln.text == '自然木鳞兽')
    assert barkion.num == 8260 and barkion.score == 1.0 and not barkion.note   # nickname: 自然木鳞龙


def test_header_styles():
    lines, headers = importer.parse('【主卡组】*40\n【怪兽卡】*1\nA*1\n【EX卡组】×1\nB*1\n【随便写的】\nC*1\nMain Deck:\nD\nSide Deck: 1\nE')
    assert [(ln.text, ln.section, ln.kind) for ln in lines] == [
        ('A', 'main', 'monster'), ('B', 'extra', 'extra'), ('C', 'extra', 'extra'), ('D', 'main', ''), ('E', 'side', '')]


def test_bracketless_headers_and_side(tf6_db, tfsp_db, names):
    for db in (tf6_db, tfsp_db):
        res = _run('import_junk.txt', db, names)              # 主卡组*40 / 怪兽卡*22 / ex卡组*15 / 副卡组*12
        assert (len(res.main), len(res.extra), len(res.side)) == (40, 15, 12) and res.unresolved == []
        assert next(ln.num for ln in res.lines if ln.text == '狐火花') == 7568   # typo for 孤火花 (limit 2)
        mirror = next(ln for ln in res.lines if ln.text == '汉诺崇高之力')
        assert mirror.num == 4887 and mirror.section == 'side'          # nickname variant, fuzzy
    sp = _run('import_junk.txt', tfsp_db, names)
    assert next(ln.num for ln in sp.lines if ln.text == '不明同调士') == 9473   # TF6 name in a TFSP import


def test_english_list_with_counted_headers(tf6_db, tfsp_db, names):
    sp = _run('import_morphtronic_en.txt', tfsp_db, names)               # "Monster Cards 19", "Traps 6" …
    assert sp.unresolved == [] and sp.warnings == [] and (len(sp.main), len(sp.extra)) == (40, 15)
    got = {ln.text: ln.num for ln in sp.lines}
    assert got['Morpthronic Scopen'] == 8168                              # typo still finds Scopen
    assert got['Mystical Space Typhoon'] == 4909 and got['Number 17: Leviathan Dragon'] == 9656
    tf6 = _run('import_morphtronic_en.txt', tf6_db, names)               # no Xyz / later cards in TF6
    assert [ln.text for ln in tf6.unresolved] == ['Vulcan the Divine', 'Stardust Spark Dragon', 'Daigusto Emeral',
                                                  'Gagaga Cowboy', 'Evilswarm  Exciton Knight']
    assert all('本游戏没有' in ln.note for ln in tf6.unresolved) and len(tf6.main) == 40
