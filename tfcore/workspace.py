"""User workspace: settings, catalog cache, backups and the optional ygocdb names, all under one
home folder (default %LOCALAPPDATA%\\TFDeckStudio). Holds no game data until the user adds some.
"""
import glob, json, os

from . import cardsource, catalog, deckcatalog, device, mydecks, pools, ygocdb, ygoprodeck
from .games import game_for_save_dir
from .savefolder import SaveFolder
from .tf6save import TF6Save

DEFAULT_HOME = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'TFDeckStudio')


class Workspace:
    def __init__(self, home=DEFAULT_HOME):
        self.home = home
        self.cache, self.backups = os.path.join(home, 'cache'), os.path.join(home, 'backups')
        self.names_path = os.path.join(home, 'ygocdb', 'cards.json')
        os.makedirs(self.cache, exist_ok=True)
        self.config_path = os.path.join(home, 'config.json')
        self.config = {'recent_saves': [], 'language': 'zh'}
        if os.path.exists(self.config_path):
            with open(self.config_path, encoding='utf-8') as f:
                self.config.update(json.load(f))
        self._names = None
        self.wiki = deckcatalog.WikiStore(home)
        self.ygopro = ygoprodeck.Store(home)
        self.passcodes = ygoprodeck.PasscodeCache(home)
        self.drafts = mydecks.Drafts(home)
        self.library = mydecks.Library(home)

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=1)

    # ---- card data
    def catalogs(self):
        out = []
        for folder in sorted(glob.glob(os.path.join(self.cache, '*-*'))):
            try:
                out.append(catalog.Catalog(folder))
            except (OSError, ValueError, KeyError):
                pass            # stale or half-built cache; the user can rebuild it
        return out

    def add_iso(self, path, progress=None):
        return catalog.Catalog(catalog.build(path, self.cache, progress=progress))

    def names_db(self):
        if self._names is None and os.path.exists(self.names_path):
            self._names = ygocdb.load(self.names_path)
        return self._names

    def download_names(self):
        ygocdb.download(os.path.dirname(self.names_path))
        self._names = None
        return self.names_db()

    # ---- saves
    @staticmethod
    def find_saves(path):
        """Tag Force save folders at `path`: the folder itself, or inside it, PSP/SAVEDATA or SAVEDATA."""
        path = os.path.abspath(path)
        if game_for_save_dir(os.path.basename(path)) and os.path.exists(os.path.join(path, 'DATA0')):
            return [path]
        found = []
        for base in (path, os.path.join(path, 'SAVEDATA'), os.path.join(path, 'PSP', 'SAVEDATA')):
            if os.path.isdir(base):
                for name in sorted(os.listdir(base)):
                    full = os.path.join(base, name)
                    if game_for_save_dir(name) and os.path.exists(os.path.join(full, 'DATA0')):
                        found.append(full)
        return found

    def pick_source(self, game, used_in_save=()):
        """Best card source for a save of `game` (see cardsource)."""
        layout = game.decks_supported                     # trunk layout known (TF6 only so far)
        cats = [c for c in self.catalogs() if c.game == game.short]
        cats.sort(key=lambda c: c.language != self.config.get('language'))
        names = self.names_db()
        if cats:
            return cardsource.from_catalog(cats[0], names, trunk_layout=layout)
        pool = pools.load(game.short) or pools.Pool(game.short, used_in_save)
        if names:
            return cardsource.from_names(names, game, pool, trunk_layout=layout)
        return cardsource.numbers_only(game, pool, trunk_layout=layout)

    # ---- handheld
    def device(self, transport=None):
        """Device for the configured handheld (config 'device': {host, key})."""
        if transport is None:
            cfg = self.config.get('device') or {}
            if not cfg.get('host'):
                raise device.DeviceError('no handheld configured')
            transport = device.SSHTransport(cfg['host'], cfg.get('key') or device.DEFAULT_KEY)
        return device.Device(transport)

    def mirror_root(self, dev):
        return os.path.join(self.home, 'device', getattr(dev.t, 'host', 'local').replace(':', '_'))

    def pull(self, name, dev=None):
        """Copy a save from the handheld into the workspace mirror and open it."""
        dev = dev or self.device()
        return self.open_save(dev.pull(name, self.mirror_root(dev)), dev)

    def open_save(self, path, dev=None):
        session = Session(self, SaveFolder(path), dev)
        recent = [p for p in self.config['recent_saves'] if p != session.folder.path]
        self.config['recent_saves'] = [session.folder.path] + recent[:7]
        self.save_config()
        return session


class Session:
    """An open save plus its card source."""

    def __init__(self, ws, folder, dev=None):
        self.ws, self.folder = ws, folder
        self.device_meta = device.Device.meta(folder.path)       # set when pulled from a handheld
        if self.device_meta and dev is None and (ws.config.get('device') or {}).get('host') == self.device_meta['host']:
            dev = ws.device()
        self.dev = dev if self.device_meta else None
        self.game = folder.game
        self.save = TF6Save(folder.plain, self.game) if self.game.decks_supported else None
        self.read_only = self.save is None
        used = set()
        if self.save:
            for d in self.save.decks().values():
                used.update(d.main + d.extra + d.side)
        self.source = ws.pick_source(self.game, used)

    @property
    def banlist(self):
        """Whether the save's ban list applies (a per-game setting; on by default)."""
        return self.ws.config.get('banlist', {}).get(self.game.short, True)

    def set_banlist(self, on):
        self.ws.config.setdefault('banlist', {})[self.game.short] = bool(on)
        self.ws.save_config()

    def trunk(self, num):
        """(owned, allowed) or None when the source cannot map cards to the trunk. With the ban
        list off every card is allowed 3 copies; owned counts still apply."""
        if not (self.save and self.source.has_trunk):
            return None
        row = self.source.row_of(num)
        if not row:
            return None
        owned, allowed = self.save.trunk(row)[:2]
        return owned, allowed if self.banlist else 3

    def problems(self, deck):
        if self.save and self.source.has_trunk:
            return self.save.problems(deck, self.source, banlist=self.banlist)
        out = []                                   # no trunk mapping: sizes and plain 3-copy rule only
        if not 40 <= len(deck.main) <= 60:
            out.append(f'main deck has {len(deck.main)} cards (40–60)')
        for sec, label in ((deck.extra, 'extra'), (deck.side, 'side')):
            if len(sec) > 15:
                out.append(f'{label} deck has {len(sec)} cards (max 15)')
        counts = {}
        for n in deck.main + deck.extra:
            counts[n] = counts.get(n, 0) + 1
        out += [f'{self.source.name_of(n, str(n))} ×{k} (max 3)' for n, k in counts.items() if k > 3]
        return out

    def commit(self, decks):
        """Write {slot: Deck} into the save file (backup first); returns the backup folder."""
        if self.read_only:
            raise PermissionError(f'{self.game.short} saves are read-only for now')
        for slot, deck in decks.items():
            self.save.write_deck(slot, deck)
        backup = self.folder.write(self.save.data, self.ws.backups)
        self.save = TF6Save(self.folder.plain, self.game)
        return backup

    def push(self):
        """Send the (already written) mirror back to the handheld; returns the device backup path."""
        if not self.dev:
            raise device.DeviceError('this save was not pulled from a handheld')
        return self.dev.push(self.folder.path)
