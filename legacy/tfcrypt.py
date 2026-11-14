"""PSP savedata crypto for Tag Force saves (sceChnnlsv modes 1/3/5).

Ported from PPSSPP Core/HLE/sceChnnlsv.cpp and Core/Dialog/SavedataParam.cpp
(GPL-2.0+); the KIRK key vault is read from PPSSPP's ext/libkirk/kirk_engine.c.

Encryption reuses the 16-byte header of an existing save, so re-encrypting an
unchanged plaintext reproduces the original file byte-for-byte.

  python -I tfcrypt.py verify  <savedir> <key>
  python -I tfcrypt.py decrypt <savedir> <key> <out.plain>
  python -I tfcrypt.py encrypt <savedir> <key> <in.plain> <outdir>
"""
import os, re, struct, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HERE = os.path.dirname(os.path.abspath(__file__))

KEY19CC = bytes.fromhex('7044A3AEEF5DA5F2857FF2D694F5363B')
KEY19DC = bytes.fromhex('EC6D29592635A57F972A0DBCA3263300')
KEY199C = bytes.fromhex('36A53EACC5269EA383D9EC256C484872')
KEY19AC = bytes.fromhex('D8C0B0F33E6B7685FDFB4D7D451E9203')
HASH198C = bytes.fromhex('FAAA50EC2FDE5493AD14B2CEA53005DF')
HASH19BC = bytes.fromhex('CB15F407F96A523C04B9B2EE5C53FA86')


def load_keyvault(path=os.path.join(HERE, 'kirk_engine.c')):
    src = open(path, encoding='latin-1').read()
    body = src[src.index('keyvault[0x80][0x10]'):]
    body = body[body.index('{') + 1:]
    kv = bytes(int(n, 16) for n in re.findall(r'0x([0-9A-Fa-f]{2})\b', body[:body.index('};')]))
    assert len(kv) == 0x800, len(kv)
    return [kv[i * 16:(i + 1) * 16] for i in range(0x80)]


KV = load_keyvault()


def xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def aes_cbc(key, iv, data, encrypt):
    c = Cipher(algorithms.AES(key), modes.CBC(iv))
    op = c.encryptor() if encrypt else c.decryptor()
    return op.update(data) + op.finalize()


def type_from_mode(mode):
    return 83 if mode in (1, 2) else 87 if mode in (3, 4) else 100


def num_from_mode(mode):
    return {1: 3, 2: 5, 3: 12, 4: 13, 6: 17}.get(mode, 16)


def num_from_mode2(mode):
    return 4 if mode == 1 else 14 if mode == 3 else 18


class FuseUnavailable(Exception):
    """Modes 2/4/6 need the per-console fuse key (KIRK CMD5), which PPSSPP lacks too."""


# ---- cipher (sceSdCipher*) ----

def keystream(mode, header, gamekey, length):
    if mode in (2, 4, 6):
        raise FuseUnavailable
    t = type_from_mode(mode)
    crypted = xor(header, gamekey) if gamekey else header
    seed = xor(crypted, KEY19AC) if t == 87 else xor(crypted, KEY19DC) if t == 100 else crypted
    k = aes_cbc(KV[num_from_mode2(mode)], bytes(16), seed, False)
    k = xor(k, KEY199C) if t == 87 else xor(k, KEY19CC) if t == 100 else k
    out = bytearray()
    ctr = 1
    for off in range(0, length, 2048):
        n = min(2048, length - off) // 16
        iv = bytes(16) if ctr == 1 else k[:12] + struct.pack('<I', ctr - 1)
        blocks = b''.join(k[:12] + struct.pack('<I', ctr + i) for i in range(n))
        ctr += n
        out += aes_cbc(KV[t], iv, blocks, False)
    return bytes(out)


# ---- MAC (sceSdMac*) ----

def _dbl(b):
    v = (int.from_bytes(b, 'big') << 1) & ((1 << 128) - 1)
    if b[0] & 0x80:
        v ^= 0x87
    return v.to_bytes(16, 'big')


def mac(mode, data, gamekey=None):
    """sceSdMacInit/Update(data)/Final; data length must be a multiple of 16 here."""
    num = num_from_mode(mode)
    key = KV[num]
    # Update keeps the final (up to 16-byte) block pending; the rest is CBC-MAC'd.
    tail_len = len(data) % 16 or 16
    body, tail = data[:len(data) - tail_len], data[len(data) - tail_len:]
    result = bytes(16)
    if body:
        result = aes_cbc(key, result, body, True)[-16:]
    k1 = _dbl(aes_cbc(key, bytes(16), bytes(16), True))
    if len(tail) < 16:
        k1 = _dbl(k1)
        tail = tail + b'\x80' + bytes(15 - len(tail))
    h = aes_cbc(key, bytes(16), xor(xor(tail, k1), result), True)
    if mode in (3, 4):
        h = xor(h, HASH198C)
    elif mode in (5, 6):
        h = xor(h, HASH19BC)
    if mode in (2, 4, 6):
        raise FuseUnavailable
    if gamekey:
        h = aes_cbc(key, bytes(16), xor(h, gamekey), True)
    return h


# ---- DATA0 ----

def decrypt_data(mode, enc, gamekey):
    body = enc[16:]
    pad = -len(body) % 16
    return xor(body + bytes(pad), keystream(mode, enc[:16], gamekey, len(body) + pad))[:len(body)]


def encrypt_data(mode, header, plain, gamekey):
    pad = -len(plain) % 16
    ct = xor(plain + bytes(pad), keystream(mode, header, gamekey, len(plain) + pad))
    blob = header + ct
    return blob[:16 + len(plain)], mac(mode, blob, gamekey)


# ---- PARAM.SFO ----

def sfo_entries(sfo):
    _, _, kt, dt, n = struct.unpack_from('<4sIIII', sfo)
    out = {}
    for i in range(n):
        ko, fmt, ln, mx, do = struct.unpack_from('<HHIII', sfo, 20 + i * 16)
        name = sfo[kt + ko:sfo.index(b'\0', kt + ko)].decode()
        out[name] = (dt + do, ln, mx)
    return out


def sfo_crypt_mode(sfo):
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    b = sfo[off]
    # GetSaveCryptMode: bit 0 set means hashed; bits 4-6 give the new modes.
    return 5 if b & 0x40 else 3 if b & 0x20 else 1 if b & 1 else 0


def file_hash(sfo, filename=b'DATA0'):
    off, ln, _ = sfo_entries(sfo)['SAVEDATA_FILE_LIST']
    for e in range(off, off + ln, 32):
        if sfo[e:e + 13].rstrip(b'\0') == filename:
            return e + 13, sfo[e + 13:e + 29]
    raise KeyError(filename)


def sfo_params(sfo, mode):
    """SavedataParam::UpdateHash; returns the 128-byte SAVEDATA_PARAMS."""
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    s = bytearray(sfo + bytes(-len(sfo) % 16))
    s[off:off + 128] = bytes(128)
    first, second = (4, 3) if mode & 2 else (2, 0)
    if mode & 4:
        first, second = 6, 5
    try:
        h = mac(first, bytes(s))
    except FuseUnavailable:
        h = b'\x01' * 16  # what PPSSPP's BuildHash writes when CMD5 is missing
    s[off + 0x20:off + 0x30] = h
    s[off] |= 1
    if mode & 6:
        s[off] |= (mode & 6) << 4
        s[off + 0x70:off + 0x80] = mac(second, bytes(s))
    s[off + 0x10:off + 0x20] = mac(1, bytes(s))
    return bytes(s[off:off + 128])


def updated_sfo(sfo, new_hash, mode):
    s = bytearray(sfo)
    hoff, _ = file_hash(sfo)
    s[hoff:hoff + 16] = new_hash
    off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
    s[off:off + 128] = sfo_params(bytes(s), mode)
    return bytes(s)


def _read(d, f):
    return open(os.path.join(d, f), 'rb').read()


def main(argv):
    cmd, d, key = argv[1], argv[2], bytes.fromhex(argv[3])
    enc, sfo = _read(d, 'DATA0'), _read(d, 'PARAM.SFO')
    mode = sfo_crypt_mode(sfo)
    if cmd == 'verify':
        off, _, _ = sfo_entries(sfo)['SAVEDATA_PARAMS']
        _, stored = file_hash(sfo)
        plain = decrypt_data(mode, enc, key)
        re_enc, h = encrypt_data(mode, enc[:16], plain, key)
        print(f'mode {mode}, DATA0 {len(enc):#x} -> plain {len(plain):#x}')
        print('file MAC matches SFO   :', mac(mode, enc + bytes(-len(enc) % 16), key) == stored)
        print('re-encrypt == original :', re_enc == enc and h == stored)
        print('SFO params recomputed  :', sfo_params(sfo, mode) == sfo[off:off + 128])
        print('SFO rebuild == original:', updated_sfo(sfo, h, mode) == sfo)
    elif cmd == 'decrypt':
        open(argv[4], 'wb').write(decrypt_data(mode, enc, key))
    elif cmd == 'encrypt':
        plain, out = open(argv[4], 'rb').read(), argv[5]
        new_enc, h = encrypt_data(mode, enc[:16], plain, key)
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, 'DATA0'), 'wb').write(new_enc)
        open(os.path.join(out, 'PARAM.SFO'), 'wb').write(updated_sfo(sfo, h, mode))
        print(f'wrote {out}: DATA0 {len(new_enc):#x}, MAC {h.hex()}')


if __name__ == '__main__':
    main(sys.argv)
