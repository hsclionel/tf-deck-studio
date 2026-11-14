"""Ready-made decks to load into a slot: the game's own recipes (TFSP, from the user's ISO),
character decks from Yugipedia (TF6, downloaded on request) and decks the user imported from
YGOPRODeck as YDK (both games); the last two live in the workspace.

Both kinds become `Entry` rows with one shape, so the app lists and filters them the same way.
"""
import json, os
from dataclasses import dataclass, field

from . import recipes, wikidecks, ygoprodeck
from .importer import standins


@dataclass
class Entry:
    key: str                      # stable id: 'rcp:123' or 'wiki:<page>#<n>'
    name: str
    group: str                    # category label shown as a filter chip
    character: str = ''
    level: int = 0                # recipes 1..4, wiki 1..10 stars; 0 = none
    champion: bool = False
    main: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    side: list = field(default_factory=list)
    missing: list = field(default_factory=list)   # cards the game does not have (wiki only)
    source: str = ''
    url: str = ''

    @property
    def level_label(self):
        if not self.level:
            return ''
        return f'Lv{self.level}' if self.source == 'game' else f'{self.level}★'


def from_recipes(found):
    out = []
    for r in found:
        group = recipes.CATEGORY_LABEL.get(r.category, r.category)
        out.append(Entry(f'rcp:{r.index}', r.name, group, r.character, r.level, r.champion,
                         list(r.main), list(r.extra), list(r.side), source='game'))
    return out


def from_wiki(decks):
    out, seen = [], {}
    for d in decks:
        k = seen[d.page] = seen.get(d.page, -1) + 1
        out.append(Entry(f'wiki:{d.page}#{k}', d.ja_name or d.name, '角色卡组', d.character, d.stars,
                         d.stars >= 9, list(d.main), list(d.extra), list(d.side), list(d.missing),
                         source=wikidecks.SOURCE, url=d.url))
    return sorted(out, key=lambda e: (e.character, e.level))


def passcode_names(names_db):
    """passcode → display name, to name cards a game does not have."""
    return {e['id']: e.get('cn_name') or e.get('en_name') or str(e['id'])
            for e in (names_db or {}).values() if e.get('id')}


def from_ygoprodeck(saved, cards, names_db=None, limit=None, codes=None):
    """Entries for decks the user imported from YGOPRODeck, matched to this game's cards (stand-ins
    applied). Cards the game lacks are skipped and listed; `limit(num)` caps to the save's ban list."""
    if not saved:
        return []
    idx = {**ygoprodeck.passcode_index(cards, standins(cards)), **(codes or {})}
    names = passcode_names(names_db)
    out = []
    for d in saved:
        f = ygoprodeck.fit(d, idx, limit)
        out.append(Entry(f"ygopro:{d['id']}", d['name'], ygoprodeck.SOURCE, '', 0, False, f['main'], f['extra'],
                         f['side'], [names.get(pc, str(pc)) for pc in f['missing']], source=ygoprodeck.SOURCE,
                         url=d.get('url', '')))
    return out


class WikiStore:
    """Raw Yugipedia wikitext per game under <home>/wiki; resolved against the open card source
    each time, so better name data or new aliases improve the match without a new download."""

    def __init__(self, home):
        self.folder = os.path.join(home, 'wiki')

    def path(self, game):
        return os.path.join(self.folder, f'{game}_pages.json')

    def supported(self, game):
        return game in wikidecks.CATEGORY

    def has(self, game):
        return os.path.exists(self.path(game))

    def download(self, game, progress=None):
        pages = wikidecks.fetch_pages(game, progress)
        os.makedirs(self.folder, exist_ok=True)
        with open(self.path(game), 'w', encoding='utf-8') as f:
            json.dump(pages, f, ensure_ascii=False)
        return pages

    def decks(self, game, cards, names_db, extra_names=None):
        if not (names_db and self.has(game)):
            return []
        with open(self.path(game), encoding='utf-8') as f:
            pages = json.load(f)
        return wikidecks.resolve(pages, game, cards, names_db, extra_names)


MINE = '我的卡组'


def from_library(decks, cards):
    """Entries for the user's own decks (tfcore.mydecks.Library); cards this source lacks are skipped."""
    out = []
    for d in sorted(decks, key=lambda d: -d.get('saved_at', 0)):
        keep = {s: [n for n in d[s] if n in cards] for s in ('main', 'extra', 'side')}
        gone = sorted({n for s in ('main', 'extra', 'side') for n in d[s] if n not in cards})
        out.append(Entry(f"my:{d['id']}", d['name'], MINE, main=keep['main'], extra=keep['extra'],
                         side=keep['side'], missing=[f'#{n}' for n in gone], source='mine'))
    return out


def entries(source, game, store, names_db, aliases=None, saved=(), codes=None, mine=()):
    """Every catalog deck for this card source and game (`saved`: YGOPRODeck decks the user kept,
    `mine`: the user's own decks for this game)."""
    out = from_library(mine, source.cards) + from_ygoprodeck(saved, source.cards, names_db, codes=codes)
    if source.catalog is not None and source.catalog.game == game:
        out += from_recipes(source.catalog.recipes())
    if store.supported(game):
        out += from_wiki(store.decks(game, source.cards, names_db, aliases))
    return out
