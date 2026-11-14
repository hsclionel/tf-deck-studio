"""Work out which game, disc version and patch language an ISO or save folder holds, and whether
an ISO and a save belong together.

- Game: the ISO's PARAM.SFO DISC_ID; for saves, the folder name / SAVEDATA_DIRECTORY prefix.
  Fan patches keep the Japanese disc ID and title, so neither says anything about language.
- Language: the script of the card names in the ISO (CJK without kana = Chinese, kana =
  Japanese, Latin = English), confirmed by the Chinese patches' `USRDIR/zh_gb.pgf` font.
- Pairing: card numbers are Konami IDs shared across patches and between TF6 releases, so any
  ISO of the same game family works with a save, whatever its language.
"""
import hashlib, os, struct
from dataclasses import dataclass

from . import ehp, iso, savecrypto
from .games import CARDINFO_PATH, GAMES, Game, game_for_save_dir


def read_sfo(data):
    """PARAM.SFO → {key: int or str}. Patched saves store GBK text, so fall back to GBK."""
    out = {}
    _, _, kt, dt, n = struct.unpack_from('<4sIIII', data)
    for i in range(n):
        ko, fmt, ln, _, do = struct.unpack_from('<HHIII', data, 20 + i * 16)
        key = data[kt + ko:data.index(b'\0', kt + ko)].decode()
        raw = data[dt + do:dt + do + ln]
        if fmt == 0x0404:
            out[key] = struct.unpack('<I', raw)[0]
        elif fmt == 0x0204:
            text = raw.split(b'\0')[0]
            try:
                out[key] = text.decode('utf-8')
            except UnicodeDecodeError:
                out[key] = text.decode('gbk', 'replace')
        else:
            out[key] = raw
    return out


def script_language(names):
    """'zh', 'ja' or 'en' from a sample of card names."""
    kana = han = latin = 0
    for s in names:
        for ch in s:
            o = ord(ch)
            if 0x3040 <= o <= 0x30FF:
                kana += 1
            elif 0x4E00 <= o <= 0x9FFF:
                han += 1
            elif ch.isascii() and ch.isalpha() or 0xFF21 <= o <= 0xFF5A:
                latin += 1
    if kana > 0.05 * (han + kana):
        return 'ja'
    return 'zh' if han > latin else 'en'


@dataclass
class IsoInfo:
    path: str
    disc_id: str
    game: Game            # None when the disc is not a supported Tag Force
    disc_version: str
    title: str
    language: str         # 'zh' / 'ja' / 'en'
    chinese_font: bool
    cardinfo_md5: str


@dataclass
class SaveInfo:
    path: str
    game: Game
    mode: int             # 0 plain (PPSSPP EncryptSave off), 1/3/5 encrypted
    size_ok: bool
    title: str
    detail: str


def identify_iso(path):
    image = iso.open_iso(path)
    sfo = read_sfo(iso.fetch(image, 'PSP_GAME/PARAM.SFO'))
    disc_id = sfo.get('DISC_ID', '')
    game = GAMES.get(disc_id)
    language, md5 = '?', ''
    if game:
        cardinfo = iso.fetch(image, CARDINFO_PATH)
        md5 = hashlib.md5(cardinfo).hexdigest()
        m = ehp.members(cardinfo)
        names = m.get('CARD_Name_J.bin') or m['CARD_Name_R.bin']
        sample = names[:40000].decode('utf-16le', 'ignore').split('\0')
        language = script_language(sample)
    try:
        iso.locate(image, 'PSP_GAME/USRDIR/zh_gb.pgf')
        font = True
    except FileNotFoundError:
        font = False
    return IsoInfo(os.path.abspath(path), disc_id, game, sfo.get('DISC_VERSION', ''), sfo.get('TITLE', ''),
                   language, font, md5)


def identify_save(folder):
    folder = os.path.abspath(folder)
    game = game_for_save_dir(os.path.basename(folder))
    with open(os.path.join(folder, 'PARAM.SFO'), 'rb') as f:
        raw = f.read()
    sfo = read_sfo(raw)
    game = game or game_for_save_dir(sfo.get('SAVEDATA_DIRECTORY', ''))
    if game is None:
        raise ValueError(f'not a Tag Force save: {folder}')
    mode = savecrypto.sfo_crypt_mode(raw)
    size = os.path.getsize(os.path.join(folder, 'DATA0'))
    expected = game.plain_size + (16 if mode else 0)
    return SaveInfo(folder, game, mode, size == expected, sfo.get('SAVEDATA_TITLE', ''),
                    sfo.get('SAVEDATA_DETAIL', ''))


def check_pair(iso_info, save_info):
    """Problems that stop this ISO's card data from being used with this save (empty = fine)."""
    out = []
    if iso_info.game is None:
        out.append(f'{os.path.basename(iso_info.path)} is not a supported Tag Force disc ({iso_info.disc_id})')
    elif iso_info.game.short != save_info.game.short:
        out.append(f'the ISO is {iso_info.game.short} but the save is {save_info.game.short}')
    if not save_info.size_ok:
        out.append('DATA0 has an unexpected size; the save may be damaged or from another game')
    return out
