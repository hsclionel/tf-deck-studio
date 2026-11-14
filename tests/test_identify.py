import os

import pytest

from conftest import MEMSTICK, TF6_ISO, TFSP_ISO
from tfcore.identify import check_pair, identify_iso, identify_save, script_language


def _iso(path):
    if not os.path.exists(path):
        pytest.skip(f'ISO not found: {path}')
    return identify_iso(path)


def test_identifies_isos():
    tf6, sp = _iso(TF6_ISO), _iso(TFSP_ISO)
    assert (tf6.disc_id, tf6.game.short, tf6.disc_version) == ('ULJM05940', 'TF6', '1.01')
    assert (sp.disc_id, sp.game.short) == ('NPJH00142', 'TFSP')
    assert tf6.language == sp.language == 'zh' and tf6.chinese_font and sp.chinese_font
    assert tf6.cardinfo_md5.startswith('846488f2')


def test_identifies_saves():
    tf6 = identify_save(MEMSTICK / 'ULJM059400001')
    sp = identify_save(MEMSTICK / 'NPJH001420001')
    assert (tf6.game.short, tf6.mode, tf6.size_ok) == ('TF6', 5, True)
    assert (sp.game.short, sp.mode, sp.size_ok) == ('TFSP', 5, True)
    assert 'TAG FORCE SPECIAL' in sp.detail          # GBK text from the patched game


def test_pairing():
    tf6_iso, sp_iso = _iso(TF6_ISO), _iso(TFSP_ISO)
    tf6_save = identify_save(MEMSTICK / 'ULJM059400001')
    assert check_pair(tf6_iso, tf6_save) == []
    assert 'TFSP but the save is TF6' in ' '.join(check_pair(sp_iso, tf6_save))


def test_script_language():
    assert script_language(['青眼白龙', '强欲之壶']) == 'zh'
    assert script_language(['青眼の白龍', 'ブラック・マジシャン']) == 'ja'
    assert script_language(['Blue-Eyes White Dragon', 'Pot of Greed']) == 'en'
