import shutil

import pytest

from conftest import MEMSTICK
from tfcore.savefolder import SaveChanged, SaveFolder
from tfcore.tf6save import Deck, TF6Save


@pytest.fixture
def folder(tmp_path):
    dst = tmp_path / 'SAVEDATA' / 'ULJM059400001'
    shutil.copytree(MEMSTICK / 'ULJM059400001', dst)
    return dst


def test_write_backs_up_and_reloads(folder, tmp_path):
    original = (folder / 'DATA0').read_bytes()
    sf = SaveFolder(folder)
    save = TF6Save(sf.plain)
    d = save.deck(0)
    save.write_deck(4, Deck('测试', d.main, d.extra))
    backup = sf.write(save.data, tmp_path / 'backups')
    assert (tmp_path / 'backups').exists() and open(f'{backup}/DATA0', 'rb').read() == original
    again = TF6Save(SaveFolder(folder).plain)
    assert again.deck(4).name == '测试' and again.deck(4).main == d.main
    assert not list(folder.glob('*.new'))


def test_refuses_when_save_changed(folder, tmp_path):
    sf = SaveFolder(folder)
    (folder / 'DATA0').write_bytes((folder / 'DATA0').read_bytes()[:-1] + b'\0')
    with pytest.raises(SaveChanged):
        sf.write(sf.plain, tmp_path / 'backups')
    assert not (tmp_path / 'backups').exists()


def test_rejects_wrong_key(folder):
    with pytest.raises(ValueError, match='MAC'):
        SaveFolder(folder, key=bytes(16))


def test_unknown_folder(tmp_path):
    (tmp_path / 'ULUS10000').mkdir()
    with pytest.raises(ValueError):
        SaveFolder(tmp_path / 'ULUS10000')


def test_tfsp_opens(tmp_path):
    sf = SaveFolder(MEMSTICK / 'NPJH001420001')
    assert sf.game.short == 'TFSP' and len(sf.plain) == 0x48000
