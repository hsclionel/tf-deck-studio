"""Character deck recipes from Yugipedia (https://yugipedia.com, text under CC BY-SA 4.0).

Downloaded at runtime on request, like the ygocdb names; nothing ships with the app. Each
character page has a "Decks" section with a per-game subsection of {{Decklist}} templates:
name, ja_name, level (the game's 1-10 star rating) and card lists keyed by kind ("effect
monsters", "synchro monsters", "spells", "side traps", ...), one "* [[Card]] xN (notes)" per line.
English card names are mapped to card numbers through the ygocdb names download.
"""
import json, re, time, urllib.parse, urllib.request
from dataclasses import asdict, dataclass, field

from .importer import norm, standins

API = 'https://yugipedia.com/api.php'
UA = {'User-Agent': 'TFDeckStudio/0.1 (personal Tag Force deck editor)'}
CATEGORY = {'TF6': "Category:Yu-Gi-Oh! 5D's Tag Force 6 characters"}
HEADING = {'TF6': 'Tag Force 6'}
SOURCE = 'Yugipedia (CC BY-SA 4.0)'
FORMAT = 1
_EXTRA_KINDS = ('fusion', 'synchro', 'xyz', 'link')


@dataclass
class WikiDeck:
    name: str
    character: str
    stars: int
    page: str
    ja_name: str = ''
    main: list = field(default_factory=list)       # card numbers
    extra: list = field(default_factory=list)
    side: list = field(default_factory=list)
    missing: list = field(default_factory=list)    # English names not found in this game

    @property
    def url(self):
        return 'https://yugipedia.com/wiki/' + urllib.parse.quote(self.page.replace(' ', '_'))


def _api(params):
    url = API + '?' + urllib.parse.urlencode({**params, 'format': 'json', 'formatversion': 2})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def fetch_pages(game, progress=None):
    """{page title: wikitext} for every character page of `game` (a few API calls in all)."""
    titles, cont = [], {}
    while True:
        r = _api({'action': 'query', 'list': 'categorymembers', 'cmtitle': CATEGORY[game], 'cmlimit': 500, **cont})
        titles += [m['title'] for m in r['query']['categorymembers']]
        if 'continue' not in r:
            break
        cont = r['continue']
    pages = {}
    for i in range(0, len(titles), 50):
        r = _api({'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
                  'titles': '|'.join(titles[i:i + 50])})
        for p in r['query']['pages']:
            if p.get('revisions'):
                pages[p['title']] = p['revisions'][0]['slots']['main']['content']
        if progress:
            progress(len(pages), len(titles))
        time.sleep(1)
    return pages


_HEAD = re.compile(r'^(=+)\s*(.*?)\s*\1\s*$', re.M)
_ITEM = re.compile(r'^\*\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\](?:\s*[x×]\s*(\d+))?', re.M)


def _sections(text, heading):
    """Text under every `heading` subsection of the page's Deck(s) section."""
    heads = [(m.start(), m.end(), len(m.group(1)), m.group(2).strip("' ")) for m in _HEAD.finditer(text)]
    in_decks, out = False, []
    for i, (_, end, level, title) in enumerate(heads):
        if level == 2:
            in_decks = title in ('Decks', 'Deck')
        if in_decks and title == heading:
            stop = next((s for s, _, lv, _ in heads[i + 1:] if lv <= level), len(text))
            out.append(text[end:stop])
    return out


def _templates(text):
    pos = 0
    while (start := text.find('{{Decklist', pos)) >= 0:
        depth, i = 0, start
        while i < len(text):
            if text.startswith('{{', i):
                depth, i = depth + 1, i + 2
            elif text.startswith('}}', i):
                depth, i = depth - 1, i + 2
                if depth == 0:
                    break
            else:
                i += 1
        yield text[start + 10:i - 2]
        pos = i


def _params(body):
    out, key = {}, None
    for line in body.split('\n'):
        m = re.match(r'^\s*\|\s*([^=|]+?)\s*=\s*(.*)$', line)
        if m:
            key = m.group(1).strip().lower().lstrip('| ')
            out[key] = m.group(2)
        elif key:
            out[key] += '\n' + line
    return out


def _plain(s):
    s = re.sub(r'\{\{Ruby\|([^|}]*)\|[^}]*\}\}', r'\1', s)
    return re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s).strip()


def parse(title, text, game):
    """(deck name, stars, ja_name, [(section, english name, count)]) for each recipe on the page."""
    out = []
    for sec in _sections(text, HEADING[game]):
        for body in _templates(sec):
            p = _params(body)
            cards = []
            for key, val in p.items():
                if not key.endswith(('monsters', 'spells', 'traps')):
                    continue
                part = 'side' if key.startswith('side') else (
                    'extra' if any(k in key for k in _EXTRA_KINDS) and 'tuner' not in key else 'main')
                for name, n in _ITEM.findall(val):
                    cards.append((part, name.strip(), int(n or 1)))
            stars = re.match(r'\d+', p.get('level', '').strip())
            out.append((_plain(p.get('name', '')), int(stars.group()) if stars else 0, _plain(p.get('ja_name', '')), cards))
    return out


def english_index(names_db):
    """normalized English name → card number, from the ygocdb names download."""
    idx = {}
    for cid, e in names_db.items():
        if e.get('en_name'):
            idx.setdefault(norm(e['en_name']), int(cid))
    return idx


def resolve(pages, game, cards, names_db, extra_names=None):
    """WikiDecks for `game`; `cards` is the game's num → Card, `extra_names` maps more English
    names to numbers (e.g. user aliases for game-only cards)."""
    idx = {**english_index(names_db), **{norm(k): v for k, v in (extra_names or {}).items()}}
    for real, to, names, _ in standins(cards):           # e.g. TF6 has 陷阱封锁 for Wiretap
        idx.update({norm(n): to for n in names})
    decks = []
    for title, text in sorted(pages.items()):
        who = re.sub(r'\s*\(Tag Force\)$', '', title)
        for name, stars, ja, items in parse(title, text, game):
            d = WikiDeck(name or '?', who, stars, title, ja)
            for part, en, n in items:
                base = re.sub(r'\s*\([^)]*\)$', '', en)          # "Time Maiden (Tag Force 6)"
                num = idx.get(norm(en)) or idx.get(norm(base)) or idx.get(norm(en.split('/')[0]))
                if num in cards:
                    getattr(d, part).extend([num] * n)
                else:
                    d.missing.append(f'{en} ×{n}' if n > 1 else en)
            if d.main:
                decks.append(d)
    return decks


def save(decks, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'format': FORMAT, 'source': SOURCE, 'decks': [asdict(d) for d in decks]}, f, ensure_ascii=False)


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            meta = json.load(f)
    except OSError:
        return None
    return [WikiDeck(**d) for d in meta['decks']] if meta.get('format') == FORMAT else None
