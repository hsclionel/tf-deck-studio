"""Decks kept outside the save, under the workspace home.

Drafts: unsaved edits, one file per save folder (`drafts/<hash>.json`), rewritten on every change
so a page reload, a closed tab or a crash never loses them. They go away when the edits are saved
or the user drops them. Each draft deck remembers the save deck's stamp it started from, so a deck
the game changed in the meantime is reported instead of silently replaced.

Library (我的卡组): decks the user keeps by name, per game, as card numbers (`mydecks.json`). They
show in the deck catalog and load into any save of that game.
"""
import hashlib, json, os, time, uuid

FORMAT = 1
SECTIONS = ('main', 'extra', 'side')


def _read(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if data.get('format') == FORMAT else None


def _write(path, data):
    """Write through a temp file, so a crash mid-write keeps the old file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'format': FORMAT, **data}, f, ensure_ascii=False)
    os.replace(tmp, path)


def _stamp(deck):
    s = deck.get('stamp') if deck else None
    return list(s) if s else None


def changed(work, orig, removed=()):
    """{slot: deck} for the slots whose edits differ from the save (`base` = the save deck's stamp).

    Slots in `removed` come back as None: the draft has to remember deletions, or closing the tab
    would quietly bring a deleted deck back.
    """
    out = {i: None for i in removed if i not in work}
    for i, w in work.items():
        o = orig.get(i)
        if o is None and not any(w[s] for s in SECTIONS):
            continue
        if o is not None and all(w[k] == o[k] for k in ('name', *SECTIONS)):
            continue
        out[i] = {'name': w['name'], **{s: list(w[s]) for s in SECTIONS}, 'base': _stamp(o)}
    return out


def restore(work, orig, draft):
    """Put the draft into `work`, deletions included.

    Returns (restored slots, slots the save changed since, deleted slots).
    """
    restored, moved, deleted = [], [], []
    for i, d in sorted(draft.items()):
        o = orig.get(i)
        if d is None:
            if o is not None and i in work:
                work.pop(i)
                deleted.append(i)
            continue
        if o is not None and all(d[k] == o[k] for k in ('name', *SECTIONS)):
            continue                                    # already in the save (saved from another tab)
        work[i] ={'name': d['name'], **{s: list(d[s]) for s in SECTIONS}, 'stamp': o['stamp'] if o else None}
        restored.append(i)
        if d.get('base') != _stamp(o):
            moved.append(i)
    return restored, moved, deleted


class Drafts:
    def __init__(self, home):
        self.folder = os.path.join(home, 'drafts')

    def path(self, save_path):
        key = hashlib.sha1(os.path.normcase(os.path.abspath(save_path)).encode('utf-8')).hexdigest()[:16]
        return os.path.join(self.folder, key + '.json')

    def load(self, save_path):
        data = _read(self.path(save_path))
        return {int(i): d for i, d in data['decks'].items()} if data else {}

    def store(self, save_path, decks):
        """Keep `decks` ({slot: deck}, as from changed()); an empty dict removes the draft."""
        if not decks:
            self.drop(save_path)
            return
        _write(self.path(save_path), {'save': save_path, 'saved_at': time.time(),
                                      'decks': {str(i): d for i, d in decks.items()}})

    def drop(self, save_path):
        try:
            os.remove(self.path(save_path))
        except FileNotFoundError:
            pass


class Library:
    def __init__(self, home):
        self.path = os.path.join(home, 'mydecks.json')

    def load(self, game=None):
        data = _read(self.path)
        decks = data['decks'] if data else []
        return [d for d in decks if game is None or d['game'] == game]

    def find(self, game, name):
        return next((d for d in self.load(game) if d['name'] == name), None)

    def save(self, game, name, deck):
        """Keep `deck` under `name`; a deck of the same game and name is replaced. Returns its id."""
        decks = self.load()
        old = next((d for d in decks if d['game'] == game and d['name'] == name), None)
        entry = {'id': old['id'] if old else uuid.uuid4().hex[:12], 'game': game, 'name': name,
                 **{s: list(deck[s]) for s in SECTIONS}, 'saved_at': time.time()}
        _write(self.path, {'decks': [d for d in decks if d is not old] + [entry]})
        return entry['id']

    def remove(self, deck_id):
        _write(self.path, {'decks': [d for d in self.load() if d['id'] != deck_id]})
