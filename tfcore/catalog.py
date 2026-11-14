"""Build and load the per-ISO card catalog cache.

Nothing ships with the app: `build(iso_path, cache_root)` reads the user's ISO once and writes
<cache_root>/<DISC_ID>-<cardinfo md5[:8]>/ with cards.json and art/<num>_<k>.webp.
"""
import hashlib, json, os
from dataclasses import asdict

from PIL import Image

from . import art, iso, pools, recipes
from .identify import identify_iso
from .carddb import Card, CardDB
from .games import CARD_ART_PATH, CARDINFO_PATH, GAMES

FORMAT = 2


def disc_id(image):
    sfo = iso.fetch(image, 'PSP_GAME/PARAM.SFO')
    for gid in GAMES:
        if gid.encode() in sfo:
            return gid
    raise ValueError('not a supported Tag Force disc')


def build(iso_path, cache_root, with_art=True, progress=None):
    image = iso.open_iso(iso_path)
    gid = disc_id(image)
    cardinfo = iso.fetch(image, CARDINFO_PATH)
    out = os.path.join(cache_root, f'{gid}-{hashlib.md5(cardinfo).hexdigest()[:8]}')
    os.makedirs(out, exist_ok=True)
    db = CardDB(cardinfo)
    with open(os.path.join(out, 'cardinfo_jpn.ehp'), 'wb') as f:
        f.write(cardinfo)
    if with_art:
        art_dir = os.path.join(out, 'art')
        os.makedirs(art_dir, exist_ok=True)
        cardh = iso.fetch(image, CARD_ART_PATH)
        for i, (num, k, img) in enumerate(art.iter_artworks(cardh)):
            img.resize((158, 158), Image.LANCZOS).save(os.path.join(art_dir, f'{num}_{k}.webp'), quality=88)
            if num in db.cards:
                db.cards[num].arts = max(db.cards[num].arts, k + 1)
            if progress and i % 500 == 0:
                progress(i)
    info = identify_iso(iso_path) if os.path.exists(iso_path) else None
    meta = dict(format=FORMAT, disc_id=gid, game=GAMES[gid].short, iso=os.path.abspath(iso_path),
                disc_version=info.disc_version if info else '', language=info.language if info else '?',
                pool_ok=pools.matches(pools.load(GAMES[gid].short), db),
                cards=[asdict(c) for c in sorted(db.cards.values(), key=lambda c: c.num)])
    with open(os.path.join(out, 'cards.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)
    recipes.save(recipes.extract(iso.fetch(image, recipes.EBOOT)), os.path.join(out, 'recipes.json'))
    return out


class Catalog:
    """A built catalog: card table plus the raw cardinfo (for IntID row lookups)."""

    def __init__(self, folder):
        self.folder = folder
        with open(os.path.join(folder, 'cards.json'), encoding='utf-8') as f:
            meta = json.load(f)
        if meta.get('format') != FORMAT:
            raise ValueError('catalog cache is from another version; rebuild it')
        self.disc_id, self.game = meta['disc_id'], meta['game']
        self.disc_version, self.language = meta['disc_version'], meta['language']
        self.iso = meta.get('iso', '')
        self.pool_ok = meta.get('pool_ok', True)   # False: this ISO's card list differs from the built-in one
        with open(os.path.join(folder, 'cardinfo_jpn.ehp'), 'rb') as f:
            self.db = CardDB(f.read())
        for c in meta['cards']:
            if c['num'] in self.db.cards:
                self.db.cards[c['num']].arts = c['arts']
        self.cards = self.db.cards

    def recipes(self):
        """The game's own deck recipes (built lazily for catalogs made before recipes existed;
        [] when the ISO is gone or its EBOOT is encrypted)."""
        path = os.path.join(self.folder, 'recipes.json')
        found = recipes.load(path)
        if found is None and os.path.exists(self.iso):
            found = recipes.from_iso(self.iso)
            recipes.save(found, path)
        return found or []

    def art_path(self, num, k=0):
        return os.path.join(self.folder, 'art', f'{num}_{k}.webp')


__all__ = ['build', 'Catalog', 'Card', 'disc_id']
