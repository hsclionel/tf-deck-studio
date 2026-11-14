"""Command line for the library (also the manual test harness).

  python -m tfcore.cli catalog <iso> [--cache DIR] [--no-art]
  python -m tfcore.cli pool    <iso> [--names cards.json]   (developer: regenerate tfcore/pools and tfcore/gamecards)
  python -m tfcore.cli passcodes <passcodes_all.json> --names cards.json  (developer: regenerate tfcore/passcodes_alt.json)
  python -m tfcore.cli verify  <save folder>
  python -m tfcore.cli decks   <save folder> [--catalog DIR]
  python -m tfcore.cli export  <save folder> <slot> <out.json>
  python -m tfcore.cli write   <save folder> <deck.json> [--slot N] [--backups DIR] [--catalog DIR] [--force]

deck.json: {"name": "...", "main": [num, ...] or [[num, copies], ...], "extra": [...], "side": [...]}
"""
import argparse, json, os, sys

from . import catalog, gamecards, iso, pools, savecrypto, ygocdb
from .carddb import CardDB
from .games import CARDINFO_PATH
from .savefolder import SaveFolder
from .tf6save import Deck, TF6Save

DEFAULT_HOME = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'TFDeckStudio')


def _cards(spec):
    out = []
    for x in spec:
        out.extend([x[0]] * x[1] if isinstance(x, list) else [x])
    return out


def _tf6(folder):
    if not folder.game.decks_supported:
        raise SystemExit(f'{folder.game.title}: deck editing is not supported yet')
    return TF6Save(folder.plain, folder.game)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(prog='tfcore')
    sub = p.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('catalog'); c.add_argument('iso'); c.add_argument('--cache', default=os.path.join(DEFAULT_HOME, 'cache'))
    c.add_argument('--no-art', action='store_true')
    pl = sub.add_parser('pool'); pl.add_argument('iso'); pl.add_argument('--names', help='ygocdb cards.json')
    pc = sub.add_parser('passcodes'); pc.add_argument('table'); pc.add_argument('--names', required=True)
    v = sub.add_parser('verify'); v.add_argument('folder')
    d = sub.add_parser('decks'); d.add_argument('folder'); d.add_argument('--catalog')
    e = sub.add_parser('export'); e.add_argument('folder'); e.add_argument('slot', type=int); e.add_argument('out')
    w = sub.add_parser('write'); w.add_argument('folder'); w.add_argument('deck'); w.add_argument('--slot', type=int)
    w.add_argument('--backups', default=os.path.join(DEFAULT_HOME, 'backups')); w.add_argument('--catalog')
    w.add_argument('--force', action='store_true', help='write even if the rule check fails')
    a = p.parse_args(argv)

    if a.cmd == 'catalog':
        out = catalog.build(a.iso, a.cache, with_art=not a.no_art, progress=lambda i: print(f'  art {i}…'))
        cat = catalog.Catalog(out)
        print(f'{cat.disc_id} ({cat.game}): {len(cat.cards)} cards -> {out}')
        return

    if a.cmd == 'pool':
        gid = catalog.disc_id(iso.open_iso(a.iso))
        db = CardDB(iso.fetch(iso.open_iso(a.iso), CARDINFO_PATH))
        game = catalog.GAMES[gid].short
        pool = pools.from_carddb(game, db)
        if not pools.matches(pool, db):
            raise SystemExit('trunk rows do not follow card-number order in this ISO; pool not written')
        os.makedirs(pools.POOL_DIR, exist_ok=True)
        out = os.path.join(pools.POOL_DIR, f'{game}.json')
        pool.save(out)
        print(f'{game}: {len(pool)} card numbers -> {out} ({os.path.getsize(out)} bytes)')
        names = ygocdb.load(a.names) if a.names else None
        nums = gamecards.select(db, names)
        info = catalog.identify_iso(a.iso)
        label = f'{gid} v{info.disc_version} {info.language} ({os.path.basename(a.iso)})'
        out = gamecards.export(game, db, nums, label)
        print(f'{game}: {len(nums)} game-original cards -> {out} ({os.path.getsize(out) // 1024} KB)')
        return

    if a.cmd == 'passcodes':
        from . import ygoprodeck
        with open(a.table, encoding='utf-8') as f:
            table = {int(k): v for k, v in json.load(f).items()}
        main = {cid: e['id'] for cid, e in ygocdb.load(a.names).items() if e.get('id')}
        pool = set(pools.load('TF6').nums) | set(pools.load('TFSP').nums)
        alt = ygoprodeck.builtin_table(table, pool, main)
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'passcodes_alt.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'_comment': 'Other passcodes (reprints, alternate artwork) of cards in TF6/TFSP → Konami card '
                                   'number. Numbers only. Source: YGOPRODeck card API konami_id.',
                       **{str(p): k for p, k in alt.items()}}, f, indent=0)
        print(f'{len(alt)} alternate passcodes -> {out}')
        return

    folder = SaveFolder(a.folder)
    if a.cmd == 'verify':
        enc, sfo = folder.encode(folder.plain)
        print(f'{folder.game.title}: mode {folder.mode}, plain {len(folder.plain):#x}')
        print('re-encrypt identical:', enc == folder.enc, '| PARAM.SFO identical:', sfo == folder.sfo)
        if folder.mode:
            off, _, _ = savecrypto.sfo_entries(folder.sfo)['SAVEDATA_PARAMS']
            print('SFO params recomputed:', savecrypto.sfo_params(folder.sfo, folder.mode) == folder.sfo[off:off + 128])
        return

    save = _tf6(folder)
    cat = catalog.Catalog(a.catalog) if getattr(a, 'catalog', None) else None
    if a.cmd == 'decks':
        h = save.play_seconds
        print(f'{folder.game.title}, play time {int(h // 3600)}:{int(h % 3600 // 60):02}:{int(h % 60):02}')
        for i, dk in save.decks().items():
            print(f'{i:3} {dk.name!r} {len(dk.main)}/{len(dk.extra)}/{len(dk.side)} tag={dk.tag:#07x} {dk.stamp}')
            if cat:
                for msg in save.problems(dk, cat.db):
                    print('      !', msg)
    elif a.cmd == 'export':
        dk = save.deck(a.slot)
        json.dump(dict(slot=a.slot, name=dk.name, main=dk.main, extra=dk.extra, side=dk.side),
                  open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'slot {a.slot} {dk.name!r} -> {a.out}')
    elif a.cmd == 'write':
        spec = json.load(open(a.deck, encoding='utf-8'))
        slot = a.slot if a.slot is not None else spec.get('slot', save.free_slot())
        dk = Deck(spec['name'], _cards(spec['main']), _cards(spec.get('extra', [])), _cards(spec.get('side', [])))
        if cat:
            issues = save.problems(dk, cat.db)
            for msg in issues:
                print('!', msg)
            if issues and not a.force:
                raise SystemExit('rule check failed; nothing written (use --force to override)')
        save.write_deck(slot, dk)
        backup = folder.write(save.data, a.backups)
        print(f'slot {slot} {dk.name!r} written; backup: {backup}')


if __name__ == '__main__':
    main()
