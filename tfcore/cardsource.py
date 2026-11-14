"""Where card data comes from for an open save, best first:

1. an ISO catalog of the same game: ROM names and text, artwork;
2. ygocdb names (save without ISO): text cards, no artwork;
3. nothing downloaded: card numbers only.

Without an ISO, game-original cards (no real-world passcode) always come from the built-in
tfcore/gamecards file, so they are fully described in modes 2 and 3 too.

In every case the game's card pool and trunk rows come from the built-in pool (tfcore/pools), so
the card list, owned counts, ban limits and rule check behave the same with or without an ISO.
"""
from dataclasses import dataclass, field

from . import gamecards, pools, ygocdb
from .carddb import Card

GAME_ONLY = '没有这张卡的资料（添加 ISO 后显示）'


@dataclass
class CardSource:
    kind: str                       # 'iso' | 'names' | 'numbers'
    label: str
    cards: dict                     # num → Card (the game's whole pool)
    pool: object = None             # pools.Pool
    has_art: bool = False
    alt_names: dict = field(default_factory=dict)   # num → {'en': …, 'ja': …, 'sc': …}
    catalog: object = None

    @property
    def has_trunk(self):
        return self.pool is not None

    def row_of(self, num):
        if self.catalog:
            return self.catalog.db.row_of(num)
        return self.pool.row_of(num) if self.pool else 0

    def name_of(self, num, default=None):
        c = self.cards.get(num)
        return c.name if c else default

    def can_add(self, num):
        return num in self.cards


def _unknown(num, text=''):
    return Card(num=num, row=0, passcode=0, name=f'#{num}', text=text, attribute='?', frame='effect',
                level=0, atk=0, defense=0, arts=0)


def _card_from_ygocdb(cid, e):
    d = e.get('data', {})
    t = d.get('type', 0)
    attribute = 'SPELL' if t & ygocdb.T_SPELL else 'TRAP' if t & ygocdb.T_TRAP else ygocdb.ATTR.get(d.get('attribute', 0), '?')
    return Card(num=cid, row=0, passcode=e.get('id', 0), name=e.get('cn_name') or e.get('sc_name') or str(cid),
                text=(e.get('text') or {}).get('desc', ''), attribute=attribute, frame=ygocdb.frame(t),
                level=d.get('level', 0) & 0xFF, atk=max(d.get('atk', 0), -1), defense=max(d.get('def', 0), -1), arts=0,
                tuner=1 if t & ygocdb.T_TUNER else 0,
                race='' if attribute in ('SPELL', 'TRAP') else ygocdb.RACE.get(d.get('race', 0), ''))


def from_catalog(catalog, names_db=None, trunk_layout=True):
    alt = {}
    if names_db:
        alt = {n: ygocdb.names(names_db[n]) for n in catalog.cards if n in names_db}
    pool = pools.from_carddb(catalog.game, catalog.db) if trunk_layout else None
    return CardSource('iso', f'{catalog.game} · ISO {catalog.disc_version} · {catalog.language}', catalog.cards,
                      pool=pool, has_art=True, alt_names=alt, catalog=catalog)


def from_names(names_db, game, pool, trunk_layout=True):
    """Save without ISO: the built-in pool; built-in data for game-original cards, ygocdb for the rest."""
    cards, alt = {}, {}
    builtin = gamecards.load(game.short)
    for n in pool.nums:
        if n in builtin:
            cards[n] = builtin[n]
        elif n in names_db:
            cards[n] = _card_from_ygocdb(n, names_db[n])
            alt[n] = ygocdb.names(names_db[n])
        else:
            cards[n] = _unknown(n, GAME_ONLY)
    return CardSource('names', f'{game.short} · ygocdb names (no ISO)', cards,
                      pool=pool if trunk_layout else None, alt_names=alt)


def numbers_only(game, pool, trunk_layout=True):
    builtin = gamecards.load(game.short)
    return CardSource('numbers', f'{game.short} · card numbers only',
                      {n: builtin.get(n) or _unknown(n) for n in pool.nums}, pool=pool if trunk_layout else None)
