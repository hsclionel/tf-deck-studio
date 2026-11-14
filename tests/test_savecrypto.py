import pytest

from conftest import ALL_SAVES
from tfcore import savecrypto
from tfcore.games import TAG_FORCE_KEY


@pytest.mark.parametrize('folder', ALL_SAVES, ids=lambda p: p.name)
def test_round_trip_is_byte_exact(folder):
    enc, sfo = (folder / 'DATA0').read_bytes(), (folder / 'PARAM.SFO').read_bytes()
    mode = savecrypto.sfo_crypt_mode(sfo)
    assert mode == 5
    plain = savecrypto.decrypt(mode, enc, TAG_FORCE_KEY)
    _, stored_mac = savecrypto.sfo_file_hash(sfo)
    assert savecrypto.mac(mode, enc + bytes(-len(enc) % 16), TAG_FORCE_KEY) == stored_mac
    re_enc, file_mac = savecrypto.encrypt(mode, enc[:16], plain, TAG_FORCE_KEY)
    assert re_enc == enc and file_mac == stored_mac
    off, _, _ = savecrypto.sfo_entries(sfo)['SAVEDATA_PARAMS']
    assert savecrypto.sfo_params(sfo, mode) == sfo[off:off + 128]
    assert savecrypto.updated_sfo(sfo, file_mac, mode) == sfo


def test_wrong_key_fails_mac():
    folder = ALL_SAVES[0]
    enc, sfo = (folder / 'DATA0').read_bytes(), (folder / 'PARAM.SFO').read_bytes()
    _, stored = savecrypto.sfo_file_hash(sfo)
    assert savecrypto.mac(5, enc + bytes(-len(enc) % 16), bytes(16)) != stored
