"""A game save folder (e.g. .../PSP/SAVEDATA/ULJM059400001): decrypt, edit, write back safely.

Write path: re-encrypt with the old header → verify by decrypting again → back up the whole
folder → write DATA0 and PARAM.SFO via temp files + os.replace → re-read and compare.
Refuses if the files changed since they were read (the game saved in the meantime).
"""
import datetime, hashlib, os, shutil

from . import savecrypto
from .games import TAG_FORCE_KEY, game_for_save_dir

DATA, SFO = 'DATA0', 'PARAM.SFO'


class SaveChanged(Exception):
    pass


def _md5(b):
    return hashlib.md5(b).hexdigest()


class SaveFolder:
    def __init__(self, path, key=TAG_FORCE_KEY):
        self.path = os.path.abspath(path)
        self.game = game_for_save_dir(os.path.basename(self.path))
        if self.game is None and os.path.exists(os.path.join(self.path, SFO)):
            # a renamed copy: the save's own PARAM.SFO still names its directory
            from .identify import read_sfo
            self.game = game_for_save_dir(read_sfo(self._read(SFO)).get('SAVEDATA_DIRECTORY', ''))
        if self.game is None:
            raise ValueError(f'not a Tag Force save folder: {path}')
        self.key = key
        self.reload()

    def _read(self, name):
        with open(os.path.join(self.path, name), 'rb') as f:
            return f.read()

    def reload(self):
        self.enc, self.sfo = self._read(DATA), self._read(SFO)
        self.mode = savecrypto.sfo_crypt_mode(self.sfo)
        self.fingerprint = (_md5(self.enc), _md5(self.sfo))
        if self.mode == 0:
            self.plain = self.enc      # PPSSPP with EncryptSave off
        else:
            self.plain = savecrypto.decrypt(self.mode, self.enc, self.key)
            _, stored = savecrypto.sfo_file_hash(self.sfo)
            if savecrypto.mac(self.mode, self.enc + bytes(-len(self.enc) % 16), self.key) != stored:
                raise ValueError('file MAC does not match PARAM.SFO (wrong key or damaged save)')
        if len(self.plain) != self.game.plain_size:
            raise ValueError(f'{self.game.short} DATA0 is {len(self.plain):#x} bytes, expected {self.game.plain_size:#x}')

    def encode(self, plain):
        """(DATA0, PARAM.SFO) bytes for a new plaintext, verified by round trip."""
        if self.mode == 0:
            return plain, self.sfo
        enc, file_mac = savecrypto.encrypt(self.mode, self.enc[:16], plain, self.key)
        sfo = savecrypto.updated_sfo(self.sfo, file_mac, self.mode)
        if savecrypto.decrypt(self.mode, enc, self.key) != plain:
            raise AssertionError('re-encrypted DATA0 does not decrypt back')
        return enc, sfo

    def backup(self, backup_root, label='before-write'):
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
        dest = os.path.join(backup_root, f'{os.path.basename(self.path)}_{stamp}_{label}')
        n = 2
        while os.path.exists(dest):                         # two writes within the same millisecond
            dest = os.path.join(backup_root, f'{os.path.basename(self.path)}_{stamp}-{n}_{label}')
            n += 1
        shutil.copytree(self.path, dest)
        return dest

    def write(self, plain, backup_root):
        """Write a new plaintext; returns the backup folder path."""
        if (_md5(self._read(DATA)), _md5(self._read(SFO))) != self.fingerprint:
            raise SaveChanged('the save changed since it was opened; reload it first')
        enc, sfo = self.encode(bytes(plain))
        backup = self.backup(backup_root)
        for name, blob in ((DATA, enc), (SFO, sfo)):
            tmp = os.path.join(self.path, name + '.new')
            with open(tmp, 'wb') as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, os.path.join(self.path, name))
        if self._read(DATA) != enc or self._read(SFO) != sfo:
            raise IOError('written files do not read back identically')
        self.reload()
        return backup
