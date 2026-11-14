"""Device sync against a folder that mirrors the handheld's file system (no network)."""
import os, shutil

import pytest

from conftest import MEMSTICK
from tfcore import device
from tfcore.tf6save import Deck
from tfcore.workspace import Workspace


@pytest.fixture
def fake(tmp_path):
    root = tmp_path / 'brick'
    shutil.copytree(MEMSTICK, root / device.SAVES.lstrip('/'))
    return device.LocalTransport(str(root))


def _remote(fake, *parts):
    return os.path.join(fake.root, device.SAVES.lstrip('/'), *parts)


def test_list_and_pull(fake, tmp_path):
    dev = device.Device(fake)
    assert [(n, g.short) for n, g in dev.list_saves()] == [('NPJH001420001', 'TFSP'), ('ULJM059400001', 'TF6')]
    local = dev.pull('ULJM059400001', str(tmp_path / 'mirror'))
    assert open(os.path.join(local, 'DATA0'), 'rb').read() == open(_remote(fake, 'ULJM059400001', 'DATA0'), 'rb').read()
    assert device.Device.meta(local)['remote'].endswith('ULJM059400001')


def test_pull_edit_push(fake, tmp_path):
    ws = Workspace(str(tmp_path / 'home'))
    dev = ws.device(fake)
    s = ws.pull('ULJM059400001', dev)
    d = s.save.deck(0)
    s.commit({5: Deck('同步测试', d.main, d.extra)})
    backup = s.push()
    assert os.path.isdir(os.path.join(fake.root, backup.lstrip('/')))           # device-side backup
    again = ws.open_save(dev.pull('ULJM059400001', str(tmp_path / 'check')))
    assert again.save.deck(5).name == '同步测试'


def test_push_refused_while_game_runs(fake, tmp_path):
    ws = Workspace(str(tmp_path / 'home'))
    dev = ws.device(fake)
    s = ws.pull('ULJM059400001', dev)
    d = s.save.deck(0)
    s.commit({5: Deck('x', d.main, d.extra)})
    fake.running = True
    before = open(_remote(fake, 'ULJM059400001', 'DATA0'), 'rb').read()
    with pytest.raises(device.GameRunning):
        s.push()
    assert open(_remote(fake, 'ULJM059400001', 'DATA0'), 'rb').read() == before


def test_push_refused_after_game_saved(fake, tmp_path):
    ws = Workspace(str(tmp_path / 'home'))
    dev = ws.device(fake)
    s = ws.pull('ULJM059400001', dev)
    d = s.save.deck(0)
    s.commit({5: Deck('x', d.main, d.extra)})
    path = _remote(fake, 'ULJM059400001', 'DATA0')
    data = bytearray(open(path, 'rb').read())
    data[-1] ^= 1                                                                # the game saved meanwhile
    open(path, 'wb').write(bytes(data))
    with pytest.raises(device.RemoteChanged):
        s.push()
    assert open(path, 'rb').read() == bytes(data)
    assert not os.path.exists(os.path.join(fake.root, device.BACKUPS.lstrip('/')))


def test_spruce_standalone_ppsspp(tmp_path):
    # spruce keeps PSP saves under Saves/.config/ppsspp/PSP/SAVEDATA (standalone PPSSPP)
    spruce_saves = device.SAVE_ROOTS[1]
    root = tmp_path / 'spruce'
    shutil.copytree(MEMSTICK, root / spruce_saves.lstrip('/'))
    fake = device.LocalTransport(str(root))
    ws = Workspace(str(tmp_path / 'home'))
    dev = ws.device(fake)
    assert [n for n, _ in dev.list_saves()] == ['NPJH001420001', 'ULJM059400001']
    s = ws.pull('ULJM059400001', dev)
    assert device.Device.meta(s.folder.path)['remote'] == f'{spruce_saves}/ULJM059400001'
    d = s.save.deck(0)
    s.commit({5: Deck('spruce', d.main, d.extra)})
    backup = s.push()
    assert backup.startswith(spruce_saves + '_backup/') and os.path.isdir(os.path.join(root, backup.lstrip('/')))
    assert ws.open_save(ws.device(fake).pull('ULJM059400001', str(tmp_path / 'c'))).save.deck(5).name == 'spruce'


def test_running_emulator_patterns():
    calls = []

    class Probe(device.SSHTransport):
        def run(self, cmd):
            calls.append(cmd)
            return ''

    assert not Probe('h').game_running()
    assert all(p in calls[0] for p in ('[m]inarch', '[P]PSSPPSDL', '[r]etroarch')) and calls[0].startswith('ps | grep')


def test_second_push_after_another_edit(fake, tmp_path):
    ws = Workspace(str(tmp_path / 'home'))
    s = ws.pull('NPJH001420001', ws.device(fake))
    d = s.save
    first = Deck('一', [4844] + [n for n in range(3459, 3600) if n in s.source.cards][:39])
    s.commit({0: first})
    s.push()
    s.commit({1: Deck('二', first.main)})
    s.push()                                   # md5s were refreshed after the first push
    names = {i: dk.name for i, dk in ws.open_save(ws.device(fake).pull('NPJH001420001', str(tmp_path / 'c'))).save.decks().items()}
    assert names == {0: '一', 1: '二'} and d is not None
