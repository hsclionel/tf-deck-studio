"""Decks found on YGOPRODeck (https://ygoprodeck.com), brought in by the user.

The app never downloads decks from the site (its owner asked that deck data stay on the site,
GitHub AlanOC91/YGOPRODeck#530). Instead it opens the site's own deck search on the categories
that suit each game, the user exports a deck as YDK there, and pastes or opens it here. The deck is
then checked against the open game (cards it has, the save's ban list) and can be kept in the
workspace (`<home>/ygoprodeck/saved.json`) as a catalog deck for both games.
"""
import gzip, hashlib, json, os, re, urllib.error, urllib.parse, urllib.request
from collections import Counter

SITE = 'https://ygoprodeck.com/'
CARD_API = 'https://db.ygoprodeck.com/api/v7/cardinfo.php'      # the documented public API
UA = {'User-Agent': 'TFDeckStudio/0.1 (personal Tag Force deck editor)'}
SOURCE = 'YGOPRODeck'
FORMAT = 2
SECTIONS = ('main', 'extra', 'side')

# Searches on the site that fit each game: (label, site category, deck-name filter, hint).
# Checked 2026-11-01: "world championship decks" holds one deck per year 2003–2018, named
# "World Championship <year> Deck", so a year in the name filter opens exactly that deck;
# "worlds format decks" is mostly modern and the site's date filter starts in 2016, so neither
# is used. TF6 = 2010 card pool (no Xyz); TFSP = early 2015 (Xyz, first Pendulums).
SEARCHES = {
    'TF6': [
        ('Edison 环境（2010）', 'edison format decks', '', '和 TF6 同一时期，大多数卡组能直接用'),
        ('2010 世界大赛卡组', 'world championship decks', '2010', '和 TF6 同一年的世界大赛卡组'),
        ('2009 世界大赛卡组', 'world championship decks', '2009', ''),
        ('2008 世界大赛卡组', 'world championship decks', '2008', ''),
        ('Goat 环境（2005）', 'goat format decks', '', '更早的经典环境，这些卡 TF6 基本都有'),
    ],
    'TFSP': [
        ('2014 世界大赛卡组', 'world championship decks', '2014', '离 TFSP 最近的一年'),
        ('2013 世界大赛卡组', 'world championship decks', '2013', ''),
        ('2012 世界大赛卡组', 'world championship decks', '2012', ''),
        ('2011 世界大赛卡组', 'world championship decks', '2011', '超量怪兽刚出来的时候'),
        ('Edison 环境（2010）', 'edison format decks', '', '同调时代的卡组，TFSP 也都能组'),
        ('Goat 环境（2005）', 'goat format decks', '', '更早的经典环境'),
    ],
}


def search_url(category, name=''):
    """The site's deck search page with a category (and optional deck name) filled in."""
    q = {'_sft_category': category, 'sort': 'Deck Views'}
    if name:
        q['name'] = name
    return SITE + 'deck-search/?' + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def from_ydk(text, name='', url=''):
    """A deck record from YDK text (or a ydke:// link) — passcodes per section — or None."""
    from .importer import parse                     # YDK / ydke handling lives in the importer
    lines, _ = parse(text)
    deck = {sec: [] for sec in SECTIONS}
    for ln in lines:
        if ln.passcode:
            deck[ln.section] += [ln.passcode] * ln.count
    if not any(deck.values()):
        return None
    m = re.search(r'ygoprodeck\.com/deck/[\w%-]+', url or text)
    link = ('https://' + m.group(0)) if m else (url or '')
    key = hashlib.sha1(json.dumps(deck, sort_keys=True).encode()).hexdigest()[:12]
    return {'id': key, 'name': name.strip() or '导入的卡组', 'url': link, **deck}


def passcode_index(cards, standins=()):
    """passcode → game card number: the card data's own passcodes, the built-in alternate passcodes,
    and stand-ins for real cards the game lacks."""
    from .importer import builtin_alternates
    idx = {pc: n for pc, n in builtin_alternates().items() if n in cards}
    idx.update({c.passcode: n for n, c in cards.items() if c.passcode})
    for _, to, _, pc in standins:
        if pc and pc not in idx:
            idx[pc] = to
    return idx


def fit(deck, by_passcode, limit=None):
    """How `deck` fits a game: {'main'/'extra'/'side': [numbers], 'missing': [passcodes],
    'over': [(number, copies, allowed)], 'changes': int}. `limit(num)` → allowed copies (3 if None)."""
    out = {'missing': [], 'over': []}
    for sec in SECTIONS:
        out[sec] = []
        for pc in deck[sec]:
            num = by_passcode.get(pc)
            if num is None:
                out['missing'].append(pc)
            else:
                out[sec].append(num)
    copies = Counter(out['main'] + out['extra'])             # the side deck does not count (game rule)
    for num, k in copies.items():
        allowed = limit(num) if limit else 3
        if k > allowed:
            out['over'].append((num, k, allowed))
    out['changes'] = len(out['missing']) + sum(k - a for _, k, a in out['over'])
    return out


class PasscodeCache:
    """passcode -> Konami card number for passcodes the card data does not list. Real cards have
    several passcodes (reprints, alternate artwork) and the game's card numbers equal the API's
    `konami_id`. The first unknown passcode downloads the whole table once from the documented card
    API (one request, ~3.5 MB, 14.5k cards, as the API guide recommends); after that every deck
    resolves offline. Passcodes still unknown (cards newer than the download) are asked one batch at
    a time. Kept in `<home>/ygoprodeck/passcodes_all.json` and `passcodes.json` (0 = API says unknown)."""

    def __init__(self, home, opener=None):
        folder = os.path.join(home, 'ygoprodeck')
        self.path, self.all_path = os.path.join(folder, 'passcodes.json'), os.path.join(folder, 'passcodes_all.json')
        self.opener = opener or self._open
        self.known, self.bulk = self._read(self.path), self._read(self.all_path)

    @staticmethod
    def _read(path):
        try:
            with open(path, encoding='utf-8') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _write(path, table):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in sorted(table.items())}, f)

    @staticmethod
    def _open(url):
        req = urllib.request.Request(url, headers={**UA, 'Accept-Encoding': 'gzip'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(gzip.decompress(raw) if r.headers.get('Content-Encoding') == 'gzip' else raw)
        except urllib.error.HTTPError as ex:
            if ex.code == 400:                         # none of these passcodes exists
                return {}
            raise

    @staticmethod
    def _table(data):
        """{passcode: konami_id} for every card and alternate artwork id in an API answer."""
        out = {}
        for c in data.get('data', []) if isinstance(data, dict) else []:
            kid = (c.get('misc_info') or [{}])[0].get('konami_id')
            if kid:
                out[c['id']] = int(kid)
                for img in c.get('card_images', []):            # alternate artworks have their own ids
                    out.setdefault(img['id'], int(kid))
        return out

    def download_all(self):
        """The whole table in one request; returns how many passcodes it holds."""
        self.bulk = self._table(self.opener(CARD_API + '?misc=yes'))
        if self.bulk:
            self._write(self.all_path, self.bulk)
        return len(self.bulk)

    def lookup(self, passcodes):
        """Make sure `passcodes` are answered (downloads the table first, once); returns the merged table."""
        want = {p for p in passcodes if p not in self.bulk and p not in self.known}
        if want and not self.bulk:
            try:
                self.download_all()
            except (OSError, ValueError):
                pass                                    # offline or blocked: fall back to a small query
            want = {p for p in want if p not in self.bulk}
        todo = sorted(want)
        for i in range(0, len(todo), 40):
            chunk = todo[i:i + 40]
            found = self._table(self.opener(CARD_API + '?id=' + ','.join(map(str, chunk)) + '&misc=yes'))
            for p in chunk:
                self.known[p] = found.get(p, 0)
            for p, kid in found.items():
                self.known.setdefault(p, kid)
        if todo:
            self._write(self.path, self.known)
        return {**self.bulk, **self.known}

    def extra_index(self, cards):
        """passcode -> game card number for known passcodes whose card the game has."""
        return {p: kid for p, kid in {**self.bulk, **self.known}.items() if kid in cards}


def builtin_table(table, pool, main_passcodes):
    """The shipped alternate-passcode map: passcodes (from a full API table) of cards in `pool` that
    are not the card data's main passcode. IDs only, like the built-in card-number lists."""
    return {p: k for p, k in sorted(table.items()) if k in pool and main_passcodes.get(k) != p}


class Store:
    """Decks the user saved, as passcodes, shared by both games."""

    def __init__(self, home):
        self.path = os.path.join(home, 'ygoprodeck', 'saved.json')

    def load(self):
        try:
            with open(self.path, encoding='utf-8') as f:
                meta = json.load(f)
        except OSError:
            return []
        return meta['decks'] if meta.get('format') == FORMAT else []

    def has(self, deck):
        return any(d['id'] == deck['id'] for d in self.load())

    def add(self, deck):
        self._write([d for d in self.load() if d['id'] != deck['id']] + [deck])

    def remove(self, deck_id):
        self._write([d for d in self.load() if d['id'] != deck_id])

    def _write(self, decks):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump({'format': FORMAT, 'source': SOURCE, 'decks': decks}, f, ensure_ascii=False)
