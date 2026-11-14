"""PSP savedata crypto (sceChnnlsv modes 1/3/5) and PARAM.SFO hashing.

Ported from PPSSPP Core/HLE/sceChnnlsv.cpp and Core/Dialog/SavedataParam.cpp (GPL-2.0+), so
this module, and any build that includes it, is GPL. Encryption reuses the 16-byte header of the
save being replaced, so an unchanged plaintext re-encrypts to the identical file.
"""
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# KIRK CMD4/CMD7 keys used by these modes (indices into PPSSPP's libkirk key vault).
KIRK = {
    3: bytes.fromhex('9802C4E6EC9E9E2FFC634CE42FBB4668'),
    4: bytes.fromhex('99244CD258F51BCBB0619CA73830075F'),
    5: bytes.fromhex('0225D7BA63ECB94A9D237601B3F6AC17'),
    12: bytes.fromhex('8485C848750843BC9B9AECA79C7F6018'),
    13: bytes.fromhex('B5B16EDE23A97B0EA17CDBA2DCDEC46E'),
    14: bytes.fromhex('C871FDB3BCC5D2F2E2D7729DDF826882'),
    16: bytes.fromhex('32295BD5EAF7A34216C88E48FF50D371'),
    17: bytes.fromhex('46F25E8E4D2AA540730BC46E47EE6F0A'),
    18: bytes.fromhex('5DC71139D01938BC027FDDDCB0837D9D'),
    83: bytes.fromhex('AFFE8EB13DD17ED80A61241C959256B6'),
    87: bytes.fromhex('1C9BC490E3066481FA59FDB600BB2870'),
    100: bytes.fromhex('03B302E85FF381B13B8DAA2A90FF5E61'),
}
KEY19CC = bytes.fromhex('7044A3AEEF5DA5F2857FF2D694F5363B')
KEY19DC = bytes.fromhex('EC6D29592635A57F972A0DBCA3263300')
KEY199C = bytes.fromhex('36A53EACC5269EA383D9EC256C484872')
KEY19AC = bytes.fromhex('D8C0B0F33E6B7685FDFB4D7D451E9203')
HASH198C = bytes.fromhex('FAAA50EC2FDE5493AD14B2CEA53005DF')
HASH19BC = bytes.fromhex('CB15F407F96A523C04B9B2EE5C53FA86')


class FuseUnavailable(Exception):
    """Modes 2/4/6 need the per-console fuse key (KIRK CMD5), which PPSSPP lacks too."""


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def _aes(key, iv, data, encrypt):
    c = Cipher(algorithms.AES(key), modes.CBC(iv))
    op = c.encryptor() if encrypt else c.decryptor()
    return op.update(data) + op.finalize()


def _type(mode):
    return 83 if mode in (1, 2) else 87 if mode in (3, 4) else 100


def _num(mode):
    return {1: 3, 2: 5, 3: 12, 4: 13, 6: 17}.get(mode, 16)


def _num2(mode):
    return 4 if mode == 1 else 14 if mode == 3 else 18


def _keystream(mode, header, gamekey, length):
    if mode in (2, 4, 6):
        raise FuseUnavailable
    t = _type(mode)
    crypted = _xor(header, gamekey) if gamekey else header
    seed = _xor(crypted, KEY19AC) if t == 87 else _xor(crypted, KEY19DC) if t == 100 else crypted
    k = _aes(KIRK[_num2(mode)], bytes(16), seed, False)
    k = _xor(k, KEY199C) if t == 87 else _xor(k, KEY19CC) if t == 100 else k
    out, ctr = bytearray(), 1
    for off in range(0, length, 2048):
        n = min(2048, length - off) // 16
        iv = bytes(16) if ctr == 1 else k[:12] + struct.pack('<I', ctr - 1)
        blocks = b''.join(k[:12] + struct.pack('<I', ctr + i) for i in range(n))
        ctr += n
        out += _aes(KIRK[t], iv, blocks, False)
    return bytes(out)


def _dbl(b):
    v = (int.from_bytes(b, 'big') << 1) & ((1 << 128) - 1)
    if b[0] & 0x80:
        v ^= 0x87
    return v.to_bytes(16, 'big')


def mac(mode, data, gamekey=None):
    """sceSdMacInit/Update/Final over 16-aligned data."""
    if mode in (2, 4, 6):
        raise FuseUnavailable
    key = KIRK[_num(mode)]
    tail_len = len(data) % 16 or 16
    body, tail = data[:len(data) - tail_len], data[len(data) - tail_len:]
    result = _aes(key, bytes(16), body, True)[-16:] if body else bytes(16)
    k1 = _dbl(_aes(key, bytes(16), bytes(16), True))
    if len(tail) < 16:
        k1 = _dbl(k1)
        tail = tail + b'\x80' + bytes(15 - len(tail))
    h = _aes(key, bytes(16), _xor(_xor(tail, k1), result), True)
    if mode == 3:
        h = _xor(h, HASH198C)
    elif mode == 5:
        h = _xor(h, HASH19BC)
    if gamekey:
        h = _aes(key, bytes(16), _xor(h, gamekey), True)
    return h


def decrypt(mode, enc, gamekey):
    body = enc[16:]
    pad = -len(body) % 16
    return _xor(body + bytes(pad), _keystream(mode, enc[:16], gamekey, len(body) + pad))[:len(body)]


def encrypt(mode, header, plain, gamekey):
    """Returns (DATA0 bytes, file MAC for SAVEDATA_FILE_LIST)."""
    pad = -len(plain) % 16
    ct = _xor(plain + bytes(pad), _keystream(mode, header, gamekey, len(plain) + pad))
    blob = header + ct
    return blob[:16 + len(plain)], mac(mode, blob, gamekey)


# ---- PARAM.SFO

def sfo_entries(sfo):
    _, _, kt, dt, n = struct.unpack_from('<4sIIII', sfo)
    out = {}
    for i in range(n):
        ko, _, ln, mx, do = struct.unpack_from('<HHIII', sfo, 20 + i * 16)
        out[sfo[kt + ko:sfo.index(b'\0', kt + ko)].decode()] = (dt + do, ln, mx)
    return out


def sfo_crypt_mode(sfo):
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    b = sfo[off]
    return 5 if b & 0x40 else 3 if b & 0x20 else 1 if b & 1 else 0


def sfo_file_hash(sfo, filename=b'DATA0'):
    """(offset, 16-byte MAC) of a file's SAVEDATA_FILE_LIST entry."""
    off, ln, _ = sfo_entries(sfo)['SAVEDATA_FILE_LIST']
    for e in range(off, off + ln, 32):
        if sfo[e:e + 13].rstrip(b'\0') == filename:
            return e + 13, sfo[e + 13:e + 29]
    raise KeyError(filename)


def sfo_params(sfo, mode):
    """SavedataParam::UpdateHash: the 128-byte SAVEDATA_PARAMS for this SFO."""
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    s = bytearray(sfo + bytes(-len(sfo) % 16))
    s[off:off + 128] = bytes(128)
    first, second = (4, 3) if mode & 2 else (2, 0)
    if mode & 4:
        first, second = 6, 5
    try:
        h = mac(first, bytes(s))
    except FuseUnavailable:
        h = b'\x01' * 16  # what PPSSPP writes when CMD5 is missing
    s[off + 0x20:off + 0x30] = h
    s[off] |= 1
    if mode & 6:
        s[off] |= (mode & 6) << 4
        s[off + 0x70:off + 0x80] = mac(second, bytes(s))
    s[off + 0x10:off + 0x20] = mac(1, bytes(s))
    return bytes(s[off:off + 128])


def updated_sfo(sfo, file_mac, mode):
    s = bytearray(sfo)
    hoff, _ = sfo_file_hash(sfo)
    s[hoff:hoff + 16] = file_mac
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    s[off:off + 128] = sfo_params(bytes(s), mode)
    return bytes(s)
