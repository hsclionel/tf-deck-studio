"""Optional card names from ygocdb.com, downloaded at runtime into the user's cache (never
bundled; the site states no licence). Keyed by `cid` = Konami card number = the value in decks.

Used two ways: extra official names (EN/JP/SC) for an ISO catalog, and the whole card table when
the user has a save but no ISO.
"""
import json, os, urllib.request, zipfile

URL = 'https://ygocdb.com/api/v0/cards.zip'

# YGOPro type / attribute bits as used by ygocdb `data`.
T_MONSTER, T_SPELL, T_TRAP = 0x1, 0x2, 0x4
T_NORMAL, T_FUSION, T_RITUAL, T_TUNER, T_SYNCHRO, T_TOKEN = 0x10, 0x40, 0x80, 0x1000, 0x2000, 0x4000
T_XYZ, T_PENDULUM, T_LINK = 0x800000, 0x1000000, 0x4000000
RACE = {0x1: '战士', 0x2: '魔法师', 0x4: '天使', 0x8: '恶魔', 0x10: '不死', 0x20: '机械', 0x40: '水', 0x80: '炎',
        0x100: '岩石', 0x200: '鸟兽', 0x400: '植物', 0x800: '昆虫', 0x1000: '雷', 0x2000: '龙', 0x4000: '兽',
        0x8000: '兽战士', 0x10000: '恐龙', 0x20000: '鱼', 0x40000: '海龙', 0x80000: '爬虫类', 0x100000: '念动力',
        0x200000: '幻神兽', 0x400000: '创造神', 0x800000: '幻龙'}
ATTR = {0x1: 'EARTH', 0x2: 'WATER', 0x4: 'FIRE', 0x8: 'WIND', 0x10: 'LIGHT', 0x20: 'DARK', 0x40: 'DIVINE'}


def download(cache_dir):
    """Fetch cards.zip and store cards.json in cache_dir; returns its path."""
    os.makedirs(cache_dir, exist_ok=True)
    zpath, out = os.path.join(cache_dir, 'cards.zip'), os.path.join(cache_dir, 'cards.json')
    req = urllib.request.Request(URL, headers={'User-Agent': 'TFDeckStudio'})
    with urllib.request.urlopen(req, timeout=60) as r, open(zpath, 'wb') as f:
        f.write(r.read())
    with zipfile.ZipFile(zpath) as z, open(out, 'wb') as f:
        f.write(z.read('cards.json'))
    os.remove(zpath)
    return out


def load(path):
    """cid → entry."""
    with open(path, encoding='utf-8') as f:
        raw = json.load(f)
    return {e['cid']: e for e in raw.values() if e.get('cid')}


def frame(t):
    if t & T_SPELL:
        return 'spell'
    if t & T_TRAP:
        return 'trap'
    for bit, name in ((T_FUSION, 'fusion'), (T_SYNCHRO, 'synchro'), (T_XYZ, 'xyz'), (T_LINK, 'link'),
                      (T_RITUAL, 'ritual'), (T_PENDULUM, 'pendulum'), (T_TOKEN, 'token'), (T_NORMAL, 'normal')):
        if t & bit:
            return name
    return 'effect'


# Display languages first; the rest are other Chinese names players use (Master Duel, forum, OCG).
NAME_FIELDS = (('zh', 'cn_name'), ('sc', 'sc_name'), ('ja', 'jp_name'), ('en', 'en_name'),
               ('md', 'md_name'), ('nw', 'nwbbs_n'), ('ocg', 'cnocg_n'))


def names(entry):
    """Names by key: zh/sc/ja/en for display, md/nw/ocg only for searching and import matching."""
    return {k: entry[f] for k, f in NAME_FIELDS if entry.get(f)}
