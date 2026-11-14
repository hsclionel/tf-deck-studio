"""TF Deck Studio — deck editor for Tag Force 6 saves, built on tfcore.

  .venv/Scripts/python app/main.py            -> http://localhost:8080 (also on the LAN)

Set TFDS_HOME to use another workspace folder (default %LOCALAPPDATA%\\TFDeckStudio).
No game data ships with the app: card data comes from the user's ISO (or, without one, from the
optional ygocdb name download), decks from the user's save folder.
"""
import argparse, collections, glob, json, os, re, sys

from fastapi import HTTPException
from fastapi.responses import FileResponse
from nicegui import app, run, ui

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tfcore import deckcatalog, device, doctor, importer, mydecks, similar, tags, wikidecks, ygoprodeck  # noqa: E402
from tfcore.identify import identify_iso, identify_save  # noqa: E402
from tfcore.savefolder import SaveChanged  # noqa: E402
from tfcore.tf6save import NSLOTS, Deck  # noqa: E402
from tfcore.workspace import DEFAULT_HOME, Workspace  # noqa: E402
from theme import ATTR, CSS, EXTRA_CSS, FRAME_LABEL as FRAME_NAMES, View, card_tile, real_card, search_key  # noqa: E402

_cli = argparse.ArgumentParser()
_cli.add_argument('--home', default=os.environ.get('TFDS_HOME', DEFAULT_HOME))
_cli.add_argument('--port', type=int, default=int(os.environ.get('TFDS_PORT', 8080)))
ARGS, _ = _cli.parse_known_args()
WS = Workspace(ARGS.home)
STATE = {'session': None}
SECTIONS = ('main', 'extra', 'side')
SEC_LABEL = {'main': '主卡组', 'extra': '额外卡组', 'side': '副卡组'}
FRAME_FILTERS = {'fusion': '融合', 'synchro': '同调', 'xyz': '超量'}
FRAME_GROUP = {'fusion': 'fusion', 'synchro': 'synchro', 'darksynchro': 'synchro', 'xyz': 'xyz'}
# Level (rank for Xyz) filter: key → (label, test).
STARS = {'1-4': ('1–4 星', lambda lv: 1 <= lv <= 4), '5-6': ('5–6 星', lambda lv: 5 <= lv <= 6),
         '7+': ('7 星以上', lambda lv: lv >= 7),
         **{str(i): (f'{i} 星', lambda lv, i=i: lv == i) for i in range(1, 13)}}
LANG_LABEL = {'zh': '中文', 'ja': '日文', 'en': '英文', '?': '未知'}


@app.get('/art/{key}/{fname}')
def art_file(key: str, fname: str):
    if not re.fullmatch(r'[A-Z0-9]+-[0-9a-f]{8}', key) or not re.fullmatch(r'\d+_\d+\.webp', fname):
        raise HTTPException(404)
    path = os.path.join(WS.cache, key, 'art', fname)
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, headers={'Cache-Control': 'max-age=86400'})


# Refreshing a section rebuilds its scroll box, which would jump back to the top. Boxes marked
# data-keep="<key>" remember their position and get it back when a box with the same key appears.
KEEP_SCROLL = '''<script>
(() => {
  const pos = {};
  document.addEventListener('scroll', e => {
    const k = e.target.dataset && e.target.dataset.keep;
    if (k) pos[k] = e.target.scrollTop;
  }, true);
  new MutationObserver(() => {
    document.querySelectorAll('[data-keep]:not([data-kept])').forEach(el => {
      el.dataset.kept = '1';
      const want = pos[el.dataset.keep] || 0;
      let tries = 60;                       // the cards render a moment after the box itself
      const put = () => {
        el.scrollTop = want;
        if (Math.abs(el.scrollTop - want) > 1 && --tries > 0) requestAnimationFrame(put);
      };
      if (want) put();
    });
  }).observe(document.body, {childList: true, subtree: true});
})();
</script>'''


# The library's rule check speaks English (tests and the command line use it); the UI shows Chinese.
_PROBLEM_ZH = (
    (re.compile(r'main deck has (\d+) cards \(40–60\)'), r'主卡组 \1 张，要 40–60 张'),
    (re.compile(r'extra deck has (\d+) cards \(max 15\)'), r'额外卡组 \1 张，最多 15 张'),
    (re.compile(r'side deck has (\d+) cards \(max 15\)'), r'副卡组 \1 张，最多 15 张'),
    (re.compile(r'card (\d+) is not in this game'), r'#\1 不是本游戏的卡'),
    (re.compile(r'(.+) belongs in the extra deck'), r'\1 应放在额外卡组'),
    (re.compile(r'(.+) belongs in the main deck'), r'\1 应放在主卡组'),
    (re.compile(r'(.+) ×(\d+), limit (\d+) \(ban list (\d+), owned (\d+)\)'), r'\1 放了 \2 张，最多 \3 张（禁限卡表 \4，持有 \5）'),
    (re.compile(r'(.+) ×(\d+) \(max 3\)'), r'\1 放了 \2 张，最多 3 张'),
)


def problem_zh(msg):
    for pat, zh in _PROBLEM_ZH:
        if pat.fullmatch(msg):
            return pat.sub(zh, msg)
    return msg


def page_frame(title_extra=None, back=False, menu=None):
    ui.add_css(CSS + EXTRA_CSS)
    ui.add_body_html(KEEP_SCROLL)
    dark = ui.dark_mode(True)
    with ui.header().classes('items-center gap-2 px-3 py-2 bg-slate-900') as header:
        if menu:
            ui.button(icon='menu', on_click=menu).props('flat round dense color=white')
        if back:
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props('flat round dense color=white')
        ui.label('TF Deck Studio').classes('text-lg font-bold text-white')
        if title_extra:
            title_extra()
        ui.space()
        ui.button(icon='dark_mode', on_click=dark.toggle).props('flat round dense color=white')
    return header


# ================================================================ start page

@ui.page('/')
def start_page():
    page_frame()
    with ui.column().classes('tf-start w-full gap-4 p-2'):
        ui.label('卡片资料取自你的游戏 ISO，卡组取自你的存档，本程序不带任何游戏数据。') \
            .classes('tf-muted text-sm')

        # ---- ISOs
        with ui.element('div').classes('tf-box w-full'):
            ui.label('① 游戏 ISO：卡片资料、效果和卡图').classes('text-base font-bold')

            @ui.refreshable
            def catalog_list():
                cats = WS.catalogs()
                if not cats:
                    ui.label('还没加 ISO。不加也能打开存档，不过只显示卡名（要先下载卡名库）或卡片编号。') \
                        .classes('tf-muted text-sm mt-1')
                for c in cats:
                    with ui.row().classes('items-center gap-2 mt-1'):
                        ui.icon('album').classes('text-green-500')
                        ui.label(f'{c.game} · {c.disc_id} · v{c.disc_version} · {LANG_LABEL.get(c.language, c.language)}补丁'
                                 f' · {len(c.cards)} 张卡').classes('font-semibold')
                        ui.label(os.path.basename(c.folder)).classes('tf-muted text-xs')
                    if not c.pool_ok:
                        ui.label('⚠ 这个 ISO 的卡表和内置编号表对不上，可能是改版补丁，存档里的持有数也许不准。')                             .classes('text-xs text-amber-500')
            catalog_list()

            async def add_iso(path):
                path = path.strip().strip('"')
                if not os.path.isfile(path):
                    ui.notify(f'找不到文件：{path}', type='negative')
                    return
                n = ui.notification(f'正在读取 {os.path.basename(path)}，大约 1 分钟…', spinner=True, timeout=None)
                try:
                    cat = await run.io_bound(WS.add_iso, path)
                    ui.notify(f'已添加 {cat.game}：{len(cat.cards)} 张卡', type='positive')
                except Exception as e:     # bad or unsupported image: show it, keep the page usable
                    ui.notify(f'无法读取这个 ISO：{e}', type='negative', multi_line=True)
                finally:
                    n.dismiss()
                catalog_list.refresh()
                found_isos.refresh()

            with ui.row().classes('w-full items-center gap-2 mt-3 no-wrap'):
                iso_in = ui.input(placeholder=r'ISO 文件路径，例如 C:\game\TagForce6.iso').props('dense outlined clearable') \
                    .classes('flex-1')
                ui.button('添加', icon='add', on_click=lambda: add_iso(iso_in.value or '')).props('unelevated no-caps')

            scan = {'dir': r'C:\game' if os.path.isdir(r'C:\game') else '', 'hits': []}

            async def do_scan():
                folder = scan_in.value.strip().strip('"')
                paths = sorted(glob.glob(os.path.join(folder, '*.iso')))
                infos = []
                for p in paths:
                    try:
                        info = await run.io_bound(identify_iso, p)
                        if info.game:
                            infos.append(info)
                    except Exception:
                        pass
                scan['hits'] = infos
                found_isos.refresh()
                if not infos:
                    ui.notify('这个文件夹里没有 Tag Force 的 ISO', type='warning')

            with ui.row().classes('w-full items-center gap-2 no-wrap'):
                scan_in = ui.input(value=scan['dir'], placeholder='或扫描一个文件夹').props('dense outlined').classes('flex-1')
                ui.button('扫描', icon='search', on_click=do_scan).props('outline no-caps')

            @ui.refreshable
            def found_isos():
                have = {os.path.basename(c.folder).split('-')[1] for c in WS.catalogs()}
                for info in scan['hits']:
                    with ui.row().classes('items-center gap-2'):
                        ui.label(f'{info.game.short} · {LANG_LABEL.get(info.language, "?")} · '
                                 f'{os.path.basename(info.path)}').classes('text-sm')
                        if info.cardinfo_md5[:8] in have:
                            ui.label('已添加').classes('text-xs text-green-500')
                        else:
                            ui.button('添加', on_click=lambda p=info.path: add_iso(p)).props('dense flat no-caps color=primary')
            found_isos()

        # ---- names
        with ui.element('div').classes('tf-box w-full'):
            ui.label('② 卡名库（可选，来自 ygocdb.com）').classes('text-base font-bold')

            @ui.refreshable
            def names_status():
                db = WS.names_db()
                if db:
                    ui.label(f'已下载：{len(db)} 张卡的官方中、日、英文名。可以用英文或日文搜索，没有 ISO 时也能显示卡名。') \
                        .classes('text-sm mt-1')
                else:
                    ui.label('还没下载（约 2.5 MB）。下载后能用官方中、日、英文卡名搜索和导入，没有 ISO 时也能显示卡名。') \
                        .classes('tf-muted text-sm mt-1')
            names_status()

            async def get_names():
                n = ui.notification('正在下载卡名库…', spinner=True, timeout=None)
                try:
                    await run.io_bound(WS.download_names)
                    ui.notify('卡名库已下载', type='positive')
                except Exception as e:     # offline or site down
                    ui.notify(f'下载失败：{e}', type='negative')
                finally:
                    n.dismiss()
                names_status.refresh()
            ui.button('下载 / 更新', icon='download', on_click=get_names).props('outline no-caps').classes('mt-2')

        # ---- saves
        with ui.element('div').classes('tf-box w-full'):
            ui.label('③ 打开存档').classes('text-base font-bold')
            ui.label('填存档文件夹（如 ULJM059400001）或记忆棒根目录都行，会自动找存档。').classes('tf-muted text-sm')
            saves = {'hits': []}

            def find():
                path = (save_in.value or '').strip().strip('"')          # clear button → None
                saves['hits'] = Workspace.find_saves(path) if path and os.path.isdir(path) else []
                save_list.refresh()
                if not saves['hits']:
                    ui.notify('没找到 Tag Force 存档', type='warning')

            with ui.row().classes('w-full items-center gap-2 mt-2 no-wrap'):
                save_in = ui.input(placeholder=r'例如 D:\PSP\SAVEDATA').props('dense outlined clearable').classes('flex-1')
                ui.button('查找', icon='folder_open', on_click=find).props('unelevated no-caps')

            def open_save(path):
                try:
                    STATE['session'] = WS.open_save(path)
                except Exception as e:     # damaged save, wrong key, unknown folder
                    ui.notify(f'无法打开存档：{e}', type='negative', multi_line=True)
                    return
                ui.navigate.to('/edit')

            def save_row(path):
                try:
                    info = identify_save(path)
                except Exception as e:
                    ui.label(f'{path}: {e}').classes('text-xs text-red-500')
                    return
                with ui.row().classes('items-center gap-2 w-full no-wrap'):
                    ui.icon('sd_card').classes('text-blue-400')
                    with ui.column().classes('gap-0 flex-1 min-w-0'):
                        ui.label(f'{info.game.short} · {os.path.basename(path)}').classes('font-semibold')
                        ui.label(f'{info.detail.replace(chr(10), " · ")}  {path}') \
                            .classes('tf-muted text-xs w-full overflow-hidden whitespace-nowrap text-ellipsis')
                    if info.game.decks_supported:
                        ui.button('打开', on_click=lambda p=path: open_save(p)).props('unelevated dense no-caps')
                    else:
                        ui.label('暂只支持识别').classes('text-xs tf-muted')

            @ui.refreshable
            def save_list():
                for p in saves['hits']:
                    save_row(p)
                recent = [p for p in WS.config['recent_saves'] if os.path.isdir(p) and p not in saves['hits']]
                if recent:
                    ui.label('最近打开').classes('text-sm font-bold mt-3')
                    for p in recent:
                        save_row(p)
            save_list()

        # ---- handheld
        with ui.element('div').classes('tf-box w-full'):
            ui.label('④ 掌机同步（SSH）').classes('text-base font-bold')
            ui.label('从掌机读取存档，改完直接写回。写回前会检查掌机上没有游戏在运行、存档没被游戏改过，'
                     '并先在掌机上备份。本程序不会启动游戏。').classes('tf-muted text-sm')
            cfg = WS.config.setdefault('device', {})
            dstate = {'saves': None, 'running': None, 'error': '', 'found': []}
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                host_in = ui.input('掌机 IP', value=cfg.get('host', '')).props('dense outlined').classes('w-44')
                key_in = ui.input('SSH 私钥文件', value=cfg.get('key') or device.DEFAULT_KEY) \
                    .props('dense outlined').classes('flex-1 min-w-[240px]')

            async def find_device():
                n = ui.notification('正在局域网里查找掌机…', spinner=True, timeout=None)
                try:
                    dstate['found'] = await run.io_bound(device.discover, key_in.value)
                finally:
                    n.dismiss()
                if dstate['found']:
                    host_in.value = dstate['found'][0][0]
                    ui.notify(f'找到 {len(dstate["found"])} 台：{", ".join(h for h, _ in dstate["found"])}', type='positive')
                else:
                    ui.notify('没找到掌机。请确认掌机已开机、开了 SSH，并和电脑连着同一个 Wi-Fi。', type='warning', multi_line=True)

            async def connect():
                cfg.update(host=host_in.value.strip(), key=key_in.value.strip())
                WS.save_config()
                dstate.update(saves=None, running=None, error='')
                try:
                    dev = WS.device()
                    dstate['saves'] = await run.io_bound(dev.list_saves)
                    dstate['running'] = await run.io_bound(dev.t.game_running)
                except Exception as e:     # unreachable host, refused key…
                    dstate['error'] = str(e)
                device_list.refresh()

            async def pull(name):
                n = ui.notification(f'正在从掌机读取 {name}…', spinner=True, timeout=None)
                try:
                    STATE['session'] = await run.io_bound(WS.pull, name)
                except Exception as e:
                    ui.notify(f'读取失败：{e}', type='negative', multi_line=True)
                    return
                finally:
                    n.dismiss()
                ui.navigate.to('/edit')

            with ui.row().classes('gap-2 mt-2'):
                ui.button('自动查找', icon='wifi_find', on_click=find_device).props('outline no-caps')
                ui.button('连接', icon='link', on_click=connect).props('unelevated no-caps')

            @ui.refreshable
            def device_list():
                if dstate['error']:
                    ui.label(f'连接失败：{dstate["error"]}').classes('text-sm text-red-500 mt-2')
                if dstate['saves'] is None:
                    return
                if dstate['running']:
                    ui.label('⚠ 掌机正在运行游戏。可以读取存档，写回前要先退回主菜单。').classes('text-sm text-amber-500 mt-2')
                else:
                    ui.label(f'已连接 {cfg["host"]}，没有游戏在运行。').classes('text-sm text-green-500 mt-2')
                if not dstate['saves']:
                    ui.label('掌机上没有 Tag Force 存档。').classes('text-sm tf-muted')
                for name, game in dstate['saves']:
                    with ui.row().classes('items-center gap-2 w-full no-wrap'):
                        ui.icon('videogame_asset').classes('text-purple-400')
                        ui.label(f'{game.short} · {name}').classes('font-semibold flex-1')
                        ui.button('读取并编辑', icon='download', on_click=lambda n=name: pull(n)) \
                            .props('unelevated dense no-caps color=purple')
            device_list()


# ================================================================ editor

@ui.page('/edit')
def edit_page():
    S = STATE['session']
    if S is None:
        ui.navigate.to('/')
        return
    src = S.source
    art_key = os.path.basename(src.catalog.folder) if src.has_art else None
    VIEWS = {}
    for num, c in src.cards.items():
        art = (lambda k, n=num: f'/art/{art_key}/{n}_{k}.webp') if art_key else None
        VIEWS[num] = View(c, art, S.trunk(num), src.can_add(num), src.alt_names.get(num, {}))
    ORDER = sorted(VIEWS.values(), key=lambda v: (v.card.attribute == '?', v.card.num))   # unnamed game-only cards last
    marks = WS.config.setdefault('staples', {}).setdefault(S.game.short, {'add': [], 'remove': []})
    favs = set(WS.config.setdefault('favorites', []))         # card numbers are the same in both games

    def retag(v):
        v.tags = frozenset(tags.tags_of(v.card, v.allowed, marks['add'], marks['remove']))

    for v in VIEWS.values():
        retag(v)

    def toggle_banlist(on):
        """The game can turn its ban list off; then every card may be played ×3 (owned still counts)."""
        S.set_banlist(on)
        for n, v in VIEWS.items():
            v.owned, v.allowed = S.trunk(n) or (None, 3)
            retag(v)
        refresh_all()
        tag_chips.refresh()
        ui.notify('已恢复使用存档的禁限卡表' if on else '已关闭禁限卡表：每张卡最多放 3 张，不超过持有数',
                  type='info' if on else 'warning')

    def originals():
        return {i: dict(name=d.name, main=list(d.main), extra=list(d.extra), side=list(d.side), stamp=d.stamp)
                for i, d in S.save.decks().items()}

    st = dict(query='', kind='all', attr=None, owned_only=src.kind != 'iso' and src.has_trunk, tags=set(), frames=set(), fav_only=False, stars=None, limit=120, tab='deck', selected=None, art={},
              multi_cards=False, multi_deck=False, pick_cards=set(), pick_deck=set(), history=[])
    st['orig'] = originals()
    st['work'] = {i: dict(d, main=list(d['main']), extra=list(d['extra']), side=list(d['side'])) for i, d in st['orig'].items()}
    st['slot'] = min(st['work']) if st['work'] else 0
    # Unsaved edits from last time (page reload, closed tab): put them back and say so.
    draft = WS.drafts.load(S.folder.path)
    st['restored'] = mydecks.restore(st['work'], st['orig'], draft) if draft else None
    st['persisted'] = json.dumps(mydecks.changed(st['work'], st['orig']), sort_keys=True)
    if st['restored']:
        st['slot'] = st['restored'][0][0]

    def persist():
        """Write the unsaved edits to the draft file (only when they changed)."""
        data = mydecks.changed(st['work'], st['orig'])
        key = json.dumps(data, sort_keys=True)
        if key != st['persisted']:
            st['persisted'] = key
            WS.drafts.store(S.folder.path, data)

    def revert(i):
        """Drop the unsaved edits of slot i: back to the save's deck (or no deck for a new slot)."""
        snapshot_slot(i)
        if i in st['orig']:
            o = st['orig'][i]
            st['work'][i] = dict(o, main=list(o['main']), extra=list(o['extra']), side=list(o['side']))
        else:
            st['work'].pop(i, None)
            if st['slot'] == i:
                st['slot'] = min(st['work']) if st['work'] else 0
        if st['restored']:
            st['restored'] = None
        refresh_all()

    def snapshot_slot(i):
        if i in st['work']:
            w = st['work'][i]
            st['history'].append((i, {k: list(v) if isinstance(v, list) else v for k, v in w.items()}))

    def deck():
        return st['work'].setdefault(st['slot'], dict(name='新卡组', main=[], extra=[], side=[], stamp=None))

    def dirty(i):
        w, o = st['work'].get(i), st['orig'].get(i)
        if o is None:
            return bool(w and (w['main'] or w['extra'] or w['side']))
        return any(w[k] != o[k] for k in ('name', 'main', 'extra', 'side'))

    def as_deck(w):
        return Deck(w['name'], list(w['main']), list(w['extra']), list(w['side']))

    def counts():
        d = deck()
        return collections.Counter(d['main'] + d['extra'] + d['side'])

    def view(n):
        return VIEWS.get(n) or View(src.cards.get(n) or _unknown(n), None, None, False, {})

    def home(n):
        return 'extra' if view(n).card.extra_deck else 'main'

    def snapshot():
        st['history'].append((st['slot'], {k: list(v) if isinstance(v, list) else v for k, v in deck().items()}))

    def change(sec, n, delta):
        if delta > 0 and not view(n).addable:
            ui.notify('本游戏没有这张卡，不能加入', type='warning')
            return
        snapshot()
        if delta > 0:
            deck()[sec].append(n)
        elif n in deck()[sec]:
            deck()[sec].remove(n)
        refresh_all()

    def undo():
        if st['history']:
            slot, data = st['history'].pop()
            st['work'][slot] = data
            st['slot'] = slot
            refresh_all()

    def toggle_multi(which):
        st[f'multi_{which}'] = not st[f'multi_{which}']
        st[f'pick_{which}'] = set()
        refresh_all()

    def add_picked(target):
        snapshot()
        for n in sorted(st['pick_cards']):
            if view(n).addable:
                deck()[home(n) if target == 'main' else 'side'].append(n)
        st['pick_cards'] = set()
        refresh_all()

    def move_picked(target):
        snapshot()
        d = deck()
        for sec, n in sorted(st['pick_deck']):
            k = d[sec].count(n)
            d[sec] = [x for x in d[sec] if x != n]
            if target:
                d[target].extend([n] * k)
        st['pick_deck'] = set()
        refresh_all()

    async def tap_card(n):
        if st['multi_cards']:
            st['pick_cards'] ^= {n}
            browser_grid.refresh()
            return
        await select(n)

    async def tap_deck(sec, n):
        if st['multi_deck']:
            st['pick_deck'] ^= {(sec, n)}
            deck_view.refresh()
            return
        await select(n)

    async def select(n):
        st['selected'] = n
        detail.refresh()
        browser_grid.refresh()
        deck_view.refresh()
        if await ui.run_javascript('window.innerWidth') < 1024:
            sheet_body.refresh()
            sheet.open()

    def refresh_all():
        persist()
        browser_grid.refresh()
        deck_view.refresh()
        detail.refresh()
        sheet_body.refresh()
        slot_list.refresh()

    def set_slot(i):
        st.update(slot=i, pick_deck=set())
        refresh_all()

    def confirm_revert(i):
        w = st['work'].get(i, {})
        with ui.dialog() as dlg, ui.card():
            ui.label(f"丢掉「{w.get('name') or '（未命名）'}」没保存的改动？").classes('font-bold')
            ui.label('卡组会回到存档里的样子。' if i in st['orig'] else '这是新卡组，会整个删掉。') \
                .classes('text-sm tf-muted')
            ui.label('丢掉后还能点「撤销」找回。').classes('text-xs tf-muted')
            with ui.row().classes('w-full justify-end'):
                ui.button('取消', on_click=dlg.close).props('flat no-caps')
                ui.button('丢掉', on_click=lambda: (dlg.close(), revert(i))).props('unelevated color=negative no-caps')
        dlg.open()

    def drop_all_restored():
        for i in list(st['restored'][0]):
            revert(i)
        ui.notify('已丢掉恢复的改动，卡组回到存档里的样子')

    # ---------- header
    def header_chips():
        ui.chip(S.game.title, icon='sports_esports').props('dense outline color=white').classes('tf-desktop-only')
        color = {'iso': 'green-7', 'names': 'amber-8', 'numbers': 'red-7'}[src.kind]
        ui.chip(src.label, icon='style').props(f'dense color={color} text-color=white').classes('tf-desktop-only')
        ui.chip(os.path.basename(S.folder.path), icon='sd_card').props('dense outline color=white').classes('tf-desktop-only')
        if S.dev:
            ui.chip(f'掌机 {S.device_meta["host"]}', icon='videogame_asset') \
                .props('dense color=purple-6 text-color=white').classes('tf-desktop-only')
    holder = {}
    page_frame(header_chips, back=True, menu=lambda: holder['drawer'].toggle())

    # ---------- slots drawer
    with ui.left_drawer(value=None).props('bordered width=260 breakpoint=1279').classes('p-2') as drawer:
        @ui.refreshable
        def slot_list():
            ui.label('存档里的卡组').classes('text-sm font-bold tf-muted px-2 pt-1')
            for i in sorted(st['work']):
                w = st['work'][i]
                active = ' active' if i == st['slot'] else ''
                with ui.element('div').classes('tf-slot' + active).on('click', lambda i=i: set_slot(i)):
                    with ui.row().classes('items-center gap-1 no-wrap w-full'):
                        ui.label(w['name'] or '（未命名）').classes('font-semibold')
                        if dirty(i):
                            ui.icon('edit').classes('tf-dirty text-sm').tooltip('有没保存的改动，已自动暂存')
                            ui.space()
                            ui.button(icon='restart_alt', on_click=lambda i=i: confirm_revert(i)) \
                                .props('flat round dense size=sm color=grey-6') \
                                .tooltip('丢掉这套卡组没保存的改动')
                    stamp = w.get('stamp')
                    when = f"{stamp[0]}-{stamp[1]:02}-{stamp[2]:02}" if stamp else '新'
                    ui.label(f"#{i} · {len(w['main'])}/{len(w['extra'])}/{len(w['side'])} · {when}").classes('text-xs tf-muted')
            free = next((i for i in range(NSLOTS) if i not in st['work']), None)
            if free is not None:
                ui.button('新建卡组', icon='add', on_click=lambda: set_slot(free)).props('flat color=primary').classes('w-full mt-1')
        slot_list()
    holder['drawer'] = drawer

    # ---------- phone tabs
    def set_tab(key):
        st['tab'] = key
        panels.refresh()
        footer_tabs.refresh()

    with ui.footer().classes('tf-mobile-only bg-slate-900 p-0'):
        @ui.refreshable
        def footer_tabs():
            with ui.row().classes('w-full no-wrap gap-0'):
                for key, icon, label in (('deck', 'style', '卡组'), ('cards', 'grid_view', '卡片'), ('slots', 'list', '列表')):
                    active = st['tab'] == key
                    ui.button(label, icon=icon, on_click=(lambda: drawer.toggle()) if key == 'slots' else (lambda k=key: set_tab(k))) \
                        .props(f"flat stack no-caps square color={'amber-5' if active else 'grey-5'}") \
                        .classes('flex-1 tf-tab' + (' tf-tab-on' if active else ''))
        footer_tabs()

    # ---------- detail
    def detail_content():
        n = st['selected']
        if n is None:
            ui.label('点一张卡查看详情').classes('tf-muted m-auto p-6')
            return
        v = view(n)
        c = v.card
        k = st['art'].get(n, 0)
        real_card(v, k)
        if c.arts > 1:
            with ui.row().classes('w-full items-center justify-center gap-2 mt-1'):
                ui.button(icon='chevron_left', on_click=lambda: (st['art'].update({n: (k - 1) % c.arts}), detail.refresh(),
                                                                 sheet_body.refresh())).props('flat round')
                ui.label(f'卡图 {k + 1}/{c.arts}').classes('text-sm')
                ui.button(icon='chevron_right', on_click=lambda: (st['art'].update({n: (k + 1) % c.arts}), detail.refresh(),
                                                                  sheet_body.refresh())).props('flat round')
        d = deck()
        in_deck = {s: d[s].count(n) for s in SECTIONS}
        with ui.element('div').classes('grid grid-cols-2 gap-2 w-full mt-3'):
            sec = home(n)
            ui.button('加入额外卡组' if sec == 'extra' else '加入主卡组', icon='add', on_click=lambda: change(sec, n, 1)) \
                .props('unelevated color=primary no-caps').classes('tf-big-btn').set_enabled(v.addable)
            ui.button('加入副卡组', icon='add', on_click=lambda: change('side', n, 1)) \
                .props('outline color=primary no-caps').classes('tf-big-btn').set_enabled(v.addable)
            rm = next((s for s in ('side', 'extra', 'main') if in_deck[s]), None)
            ui.button('移除一张', icon='remove', on_click=lambda: change(rm, n, -1)) \
                .props('outline color=negative no-caps').classes('tf-big-btn col-span-2').set_enabled(rm is not None)
        if not v.addable:
            ui.label('🔒 本游戏没有这张卡，不能加入。').classes('text-xs tf-muted mt-1')
        with ui.row().classes('w-full items-center gap-1 mt-2'):
            for key in tags.TAGS:
                if key in v.tags:
                    ui.chip(tags.TAGS[key]).props('dense outline color=primary').classes('text-xs')
            ui.space()
            staple = 'staple' in v.tags
            ui.button('取消强卡' if staple else '标为强卡', icon='star' if staple else 'star_outline',
                      on_click=lambda: toggle_staple(n)).props('flat dense no-caps size=sm color=amber-7')
            fav = n in favs
            ui.button('取消喜欢' if fav else '标为喜欢', icon='favorite' if fav else 'favorite_border',
                      on_click=lambda: toggle_fav(n)).props('flat dense no-caps size=sm color=pink-6')
        alt = src.alt_names.get(n, {})
        rows = [('编号', c.num), ('密码', c.passcode or '—'),
                ('持有', '—' if v.owned is None else v.owned),
                ('限制', '—' if v.owned is None else ['禁止', '限制 1', '准限制 2', '无限制'][v.allowed]
                 + ('' if S.banlist else '（禁限卡表已关闭）'))]
        with ui.element('div').classes('grid grid-cols-4 gap-x-2 text-xs mt-3 w-full'):
            for key, val in rows:
                ui.label(key).classes('tf-muted')
                ui.label(str(val))
        if c.game_only:
            ui.label('游戏原创卡：现实中没有这张卡，也就没有卡片密码，资料取自游戏。').classes('text-xs text-teal-500')
        for lang, label in (('en', 'EN'), ('ja', 'JP'), ('sc', '官方中文')):
            if alt.get(lang) and alt[lang] != c.name:
                ui.label(f'{label}：{alt[lang]}').classes('text-xs')
        here = ' · '.join(f'{SEC_LABEL[s]} ×{m}' for s, m in in_deck.items() if m)
        if here:
            ui.label(here).classes('text-xs mt-1')

    with ui.dialog().props('position=bottom') as sheet, \
            ui.card().classes('w-full p-3').style('max-height:88dvh; overflow:auto'):
        @ui.refreshable
        def sheet_body():
            with ui.element('div').classes('w-full').style('max-width:340px; margin:0 auto'):
                detail_content()
        sheet_body()

    # ---------- browser
    def toggle_tag(key):
        st['tags'] ^= {key}
        st['limit'] = 120
        tag_chips.refresh()
        browser_grid.refresh()

    def toggle_frame(key):
        st['frames'] ^= {key}
        st['limit'] = 120
        tag_chips.refresh()
        browser_grid.refresh()

    def chip(label, on, on_click, tip, color='primary'):
        ui.button(label, on_click=on_click) \
            .props(f"dense rounded no-caps size=sm {f'unelevated color={color}' if on else 'outline color=grey-6'}") \
            .classes('shrink-0').tooltip(tip)

    def clear_chips():
        st.update(tags=set(), frames=set(), fav_only=False, limit=120)
        tag_chips.refresh()
        browser_grid.refresh()

    @ui.refreshable
    def tag_chips():
        with ui.row().classes('w-full gap-1 tf-chiprow'):
            chip(f'♥ 喜欢 {len(favs)}' if favs else '♥ 喜欢', st['fav_only'],
                 lambda: (st.update(fav_only=not st['fav_only'], limit=120), tag_chips.refresh(), browser_grid.refresh()),
                 '只看标为喜欢的卡。在卡片详情里标记或取消', color='pink-6')
            for key, label in FRAME_FILTERS.items():
                chip(label, key in st['frames'], lambda k=key: toggle_frame(k),
                     f'{label}怪兽' + ('（含黑暗同调）' if key == 'synchro' else ''))
            for key, label in tags.TAGS.items():
                if key == 'limited' and not (src.has_trunk and S.banlist):
                    st['tags'].discard(key)
                    continue
                on = key in st['tags']
                ui.button(label, on_click=lambda k=key: toggle_tag(k)) \
                    .props(f"dense rounded no-caps size=sm {'unelevated color=primary' if on else 'outline color=grey-6'}") \
                    .classes('shrink-0').tooltip({'staple': '常见的通用强卡。名单内置，可在卡片详情里增减',
                                                  'tuner': '调整怪兽，也包括黑暗调整',
                                                  'handtrap': '对方回合从手卡发动的怪兽',
                                                  'limited': '存档禁限卡表里被禁止或限制的卡'}.get(key, '根据效果文字自动归类'))
            if st['tags'] or st['frames'] or st['fav_only']:
                ui.button(icon='close', on_click=clear_chips).props('flat round dense size=sm').classes('shrink-0').tooltip('清除这些筛选')

    def toggle_staple(n):
        key = 'remove' if 'staple' in view(n).tags else 'add'
        other = 'add' if key == 'remove' else 'remove'
        if n in marks[other]:
            marks[other].remove(n)
        elif n not in tags.staples() or key == 'remove':
            marks[key].append(n)
        WS.save_config()
        retag(view(n))
        detail.refresh()
        sheet_body.refresh()
        browser_grid.refresh()

    def toggle_fav(n):
        favs.symmetric_difference_update({n})
        WS.config['favorites'] = sorted(favs)
        WS.save_config()
        detail.refresh()
        sheet_body.refresh()
        tag_chips.refresh()
        browser_grid.refresh()

    def filtered():
        q = search_key(st['query'])
        out = []
        for v in ORDER:
            c = v.card
            if st['kind'] == 'monster' and v.is_spelltrap:
                continue
            if st['kind'] in ('SPELL', 'TRAP') and c.attribute != st['kind']:
                continue
            if st['attr'] and c.attribute != st['attr']:
                continue
            if st['frames'] and FRAME_GROUP.get(c.frame) not in st['frames']:
                continue
            if st['stars'] and (v.is_spelltrap or c.attribute == '?' or not STARS[st['stars']][1](c.level)):
                continue
            if st['fav_only'] and c.num not in favs:
                continue
            if st['owned_only'] and not (v.owned or v.owned is None):
                continue
            if st['tags'] and not st['tags'] <= v.tags:
                continue
            if q and q not in v.key and q != str(c.num) and q != str(c.passcode):
                continue
            out.append(v)
        return out

    def pickbar(text, actions, clear):
        with ui.row().classes('tf-pickbar items-center gap-1 no-wrap'):
            ui.label(text).classes('font-bold text-sm whitespace-nowrap')
            ui.space()
            for label, icon, fn in actions:
                ui.button(label, icon=icon, on_click=fn).props('unelevated dense no-caps color=grey-10')
            ui.button(icon='close', on_click=clear).props('flat round dense color=grey-10')

    @ui.refreshable
    def browser_grid():
        res, cnt = filtered(), counts()
        ui.label(f'{len(res)} 张').classes('text-xs tf-muted mb-1')
        if st['multi_cards'] and st['pick_cards']:
            pickbar(f"已选 {len(st['pick_cards'])}", [('加入主卡组', 'add', lambda: add_picked('main')),
                                                      ('加入副卡组', 'add', lambda: add_picked('side'))],
                    lambda: (st.update(pick_cards=set()), browser_grid.refresh()))
        with ui.element('div').classes('tf-grid'):
            for v in res[:st['limit']]:
                n = v.card.num
                card_tile(v, count=cnt.get(n, 0), selected=n == st['selected'], picked=n in st['pick_cards'], fav=n in favs,
                          on_click=lambda n=n: tap_card(n),
                          on_plus=None if st['multi_cards'] or not v.addable else (lambda n=n: change(home(n), n, 1)))
        if len(res) > st['limit']:
            ui.button('加载更多', on_click=lambda: (st.update(limit=st['limit'] + 120), browser_grid.refresh())) \
                .props('flat color=primary').classes('w-full mt-2')

    # ---------- deck
    @ui.refreshable
    def deck_view():
        d = deck()
        issues = [problem_zh(m) for m in S.problems(as_deck(d))] if d['main'] or d['extra'] or d['side'] else ['空卡组']
        if st['restored']:
            slots, moved = st['restored']
            with ui.element('div').classes('w-full px-3 pt-2'), \
                    ui.row().classes('w-full items-center gap-2 rounded px-2 py-1 bg-amber-1 text-amber-10'):
                ui.icon('restore')
                with ui.column().classes('gap-0 flex-1 min-w-0'):
                    names = '、'.join(f"#{i}「{st['work'][i]['name']}」" for i in slots if i in st['work'])
                    ui.label(f'恢复了上次没保存的改动：{names}').classes('text-xs')
                    if moved:
                        ui.label('其中 ' + '、'.join(f'#{i}' for i in moved) + ' 在存档里又被游戏改过，这里显示的是你上次改的版本。') \
                            .classes('text-xs text-red-700')
                ui.button('丢掉', on_click=drop_all_restored).props('flat dense no-caps size=sm color=negative')
                ui.button('知道了', on_click=lambda: (st.update(restored=None), deck_view.refresh())) \
                    .props('flat dense no-caps size=sm')
        with ui.row().classes('items-center gap-2 px-3 pt-3 w-full no-wrap'):
            ui.input(value=d['name'], on_change=lambda e: (d.update(name=e.value), persist(), slot_list.refresh(),
                                                           save_button.refresh())) \
                .props('dense borderless maxlength=63 input-class="text-lg font-bold"').classes('flex-1 min-w-0')
            ui.button('多选', icon='checklist', on_click=lambda: toggle_multi('deck')) \
                .props(f"{'unelevated color=amber-7 text-color=black' if st['multi_deck'] else 'outline'} dense no-caps")
            ui.label(f"#{st['slot']}").classes('tf-muted text-xs')
        with ui.row().classes('gap-1 px-3 pb-2'):
            for sec, lo, hi in (('main', 40, 60), ('extra', 0, 15), ('side', 0, 15)):
                ok = lo <= len(d[sec]) <= hi
                ui.chip(f'{SEC_LABEL[sec]} {len(d[sec])}', icon='check' if ok else 'error') \
                    .props(f"dense {'color=green-1 text-color=green-9' if ok else 'color=red-1 text-color=red-9'}")
            if not issues:
                ui.chip('合规', icon='verified').props('dense color=blue-1 text-color=blue-9')
            if src.has_trunk and S.save:
                on = S.banlist
                ui.chip('禁限卡表 开' if on else '禁限卡表 关', icon='gavel' if on else 'block',
                        on_click=lambda: toggle_banlist(not on)) \
                    .props(f"dense clickable {'outline color=grey-7' if on else 'color=amber-3 text-color=amber-10'}") \
                    .tooltip('点一下切换。关闭后每张卡最多放 3 张，但不超过持有数。'
                             '游戏设置里也要关掉禁限卡表，不然游戏可能不认这个卡组。')
        for msg in issues[:4]:
            ui.label('⚠ ' + msg).classes('text-xs text-red-500 px-3')
        if st['multi_deck'] and st['pick_deck']:
            secs = {s for s, _ in st['pick_deck']}
            moves = [(f'移到{SEC_LABEL[s]}', 'drive_file_move', lambda s=s: move_picked(s)) for s in SECTIONS if {s} != secs]
            pickbar(f"已选 {len(st['pick_deck'])} 种", moves + [('移除', 'delete', lambda: move_picked(None))],
                    lambda: (st.update(pick_deck=set()), deck_view.refresh()))
        with ui.element('div').classes('tf-scroll').props(f'data-keep=deck-{st["slot"]}'):
            for sec in SECTIONS:
                cnt = collections.Counter(d[sec])
                with ui.element('div').classes('tf-section-title'):
                    ui.label(SEC_LABEL[sec])
                    ui.label(str(len(d[sec]))).classes('tf-muted')
                if not cnt:
                    ui.label('—').classes('tf-muted text-xs px-1 mb-2')
                    continue
                order = sorted(cnt, key=lambda n: ({'spell': 1, 'trap': 2}.get(view(n).card.frame, 0), -view(n).card.level, n))
                with ui.element('div').classes('tf-grid mb-3'):
                    for n in order:
                        quick = not st['multi_deck']
                        card_tile(view(n), count=cnt[n], selected=n == st['selected'], picked=(sec, n) in st['pick_deck'],
                                  on_click=lambda s=sec, n=n: tap_deck(s, n),
                                  on_plus=(lambda s=sec, n=n: change(s, n, 1)) if quick and view(n).addable else None,
                                  on_minus=(lambda s=sec, n=n: change(s, n, -1)) if quick else None)
        with ui.row().classes('tf-actions no-wrap items-center gap-0 p-2 border-t w-full').style('border-color:var(--tf-line)'):
            ui.button(icon='undo', on_click=undo).props('flat round').tooltip('撤销').set_enabled(bool(st['history']))
            ui.button(icon='library_books', on_click=open_catalog).props('flat round').tooltip('卡组库：游戏内配方和网上的卡组')
            ui.button(icon='content_paste', on_click=open_import).props('flat round').tooltip('导入卡表或 YDK')
            ui.button(icon='ios_share', on_click=open_export).props('flat round').tooltip('导出为 YDK 或文本')
            ui.button(icon='bookmark_add', on_click=open_keep).props('flat round') \
                .tooltip('存到我的卡组：留在电脑上，以后能放进任何存档').set_enabled(bool(d['main'] or d['extra']))
            ui.button(icon='insights', on_click=open_doctor).props('flat round').tooltip('卡组分析：构成、上手率和建议') \
                .set_enabled(bool(d['main']))
            ui.space()
            save_button()

    @ui.refreshable
    def save_button():
        if st.get('push_pending'):
            ui.button('写回掌机', icon='upload', on_click=push).props('unelevated color=purple no-caps')                 .tooltip('上次没能写回掌机，改动已存在电脑上')
        n_dirty = sum(dirty(i) for i in st['work'])
        ui.button(f'保存（{n_dirty}）' if n_dirty else '保存', icon='save', on_click=review) \
            .props('unelevated color=primary no-caps').classes('whitespace-nowrap').tooltip('保存到存档') \
            .set_enabled(n_dirty > 0)

    # ---------- my decks
    def open_keep():
        d = deck()
        form = dict(name=d['name'] or '我的卡组')
        with ui.dialog() as dlg, ui.card().classes('w-[400px] max-w-full'):
            ui.label('存到我的卡组').classes('text-lg font-bold')
            ui.label(f'存在这台电脑上。以后打开任何一个 {S.game.short} 存档，都能从「卡组库 → {deckcatalog.MINE}」'
                     '载入，点「保存」就写进存档，连着掌机时也会写回掌机。').classes('text-xs tf-muted')
            ui.input('名字', value=form['name'],
                     on_change=lambda e: (form.update(name=(e.value or '').strip()), note.refresh())) \
                .props('dense outlined maxlength=63 autofocus').classes('w-full')

            @ui.refreshable
            def note():
                if WS.library.find(S.game.short, form['name']):
                    ui.label('已经有同名的卡组，存了会把它换掉。').classes('text-xs text-amber-600')
            note()

            def keep():
                if not form['name']:
                    ui.notify('先起个名字', type='warning')
                    return
                WS.library.save(S.game.short, form['name'], d)
                dlg.close()
                ui.notify(f'已存到我的卡组：「{form["name"]}」', type='positive')

            with ui.row().classes('w-full justify-end'):
                ui.button('取消', on_click=dlg.close).props('flat no-caps')
                ui.button('存', icon='bookmark_add', on_click=keep).props('unelevated color=primary no-caps')
        dlg.open()

    # ---------- import / export
    def aliases():
        return WS.config.setdefault('aliases', {}).setdefault(S.game.short, {})

    async def resolve_passcodes(text):
        """Other passcodes of cards the game has (83011278 is another passcode of Mystic Tomato,
        83011277): asks the documented card API once about passcodes the card data does not list."""
        have = ygoprodeck.passcode_index(src.cards, importer.standins(src.cards))
        unknown = {ln.passcode for ln in importer.parse(text)[0] if ln.passcode and ln.passcode not in have}
        if unknown - set(WS.passcodes.known) - set(WS.passcodes.bulk):
            try:
                await run.io_bound(WS.passcodes.lookup, unknown)
            except (OSError, ValueError):
                ui.notify('网络不通，查不了卡片密码。认不出的密码会当作本游戏没有的卡。', type='warning')
        return WS.passcodes.extra_index(src.cards)

    def open_import():
        imp = dict(text='', res=None, target='new', name='导入的卡组', extra={})
        free = next((i for i in range(NSLOTS) if i not in st['work']), None)
        with ui.dialog().props('maximized-mobile') as dlg, \
                ui.card().classes('w-full').style('max-width:760px; max-height:92dvh; overflow:auto'):
            ui.label('导入卡组').classes('text-lg font-bold')
            ui.label('可以粘贴论坛卡表（「卡名*3」「3x 卡名」等写法）、YDK 文件内容或 ydke:// 链接。') \
                .classes('text-xs tf-muted')
            box = ui.textarea(placeholder='【怪兽】\n命运女郎·光*3\n…').props('outlined rows=8').classes('w-full')

            async def parse():
                imp['text'] = box.value or ''
                imp['extra'] = await resolve_passcodes(imp['text'])
                imp.update(swap=None, swapped={})
                imp['res'] = importer.run(imp['text'], src, aliases(), trunk=S.trunk, names_db=WS.names_db(),
                                          passcodes=imp['extra'])
                auto_swap()
                result.refresh()

            def auto_swap():
                """Pre-pick a swap for every cut, as the deck library does (staples doing the same job first)."""
                for num, sec, lost, _ in list(imp['res'].cuts):
                    r = imp['res']
                    best = similar.similar(num, src.cards, lambda n: room(r, n), limit=1)
                    imp['swap'] = num
                    if best:
                        swap(r, sec, lost, best[0][0], quiet=True)
                    else:
                        imp.setdefault('swapped', {})[num] = (0, 0)
                imp['swap'] = None

            with ui.row().classes('gap-2'):
                ui.button('识别', icon='auto_fix_high', on_click=parse).props('unelevated color=primary no-caps')
                ui.button('取消', on_click=dlg.close).props('flat no-caps')

            def room(r, n):
                """Copies of n the imported deck may still take (copy limit, ban list, owned)."""
                if not view(n).addable:
                    return 0
                t = S.trunk(n)
                cap = min(3, *t) if t else 3
                return cap - (r.main + r.extra).count(n)

            def swap(r, sec, lost, n, quiet=False):
                k = min(lost, room(r, n))
                cut = imp['swap']
                r.lines.append(importer.Line(f'（替换 {cut}）{src.cards[n].name}', sec, k, text=src.cards[n].name,
                                             num=n, score=1.0))
                imp['res'] = importer.finish(r.lines, importer.parse(imp['text'])[1], src, trunk=S.trunk)
                imp.setdefault('swapped', {})[cut] = (n, k)
                imp['swap'] = None
                if not quiet:
                    result.refresh()

            def drop_only(num):
                imp.setdefault('swapped', {})[num] = (0, 0)
                imp['swap'] = None
                result.refresh()

            def unswap(num):
                """Take the swap for `num` back out and show the choices again."""
                imp['swapped'].pop(num, None)
                r = imp['res']
                r.lines[:] = [ln for ln in r.lines if not ln.raw.startswith(f'（替换 {num}）')]
                imp['res'] = importer.finish(r.lines, importer.parse(imp['text'])[1], src, trunk=S.trunk)
                imp['swap'] = num
                result.refresh()

            def swap_row(r, num, sec, lost, why):
                name = src.cards[num].name
                done = imp.get('swapped', {}).get(num)
                with ui.row().classes('w-full items-center gap-2 no-wrap'):
                    ui.label(f'「{name}」×{lost}（{why}）').classes('text-xs')
                    ui.icon('east').classes('tf-muted')
                    if done:
                        text = f'{src.cards[done[0]].name} ×{done[1]}' if done[0] else '只删掉，不补'
                        ui.label(text).classes('text-xs text-green-600')
                        ui.button('换别的', on_click=lambda: unswap(num)) \
                            .props('flat dense no-caps size=sm color=primary')
                        return
                    ui.label('选一张补上').classes('text-xs tf-muted')
                    ui.button('只删掉，不补', on_click=lambda: drop_only(num)) \
                        .props('flat dense no-caps size=sm color=grey-7')
                options = similar.similar(num, src.cards, lambda n: room(r, n))
                if not options:
                    ui.label('没找到效果相近、没超限的卡').classes('text-xs tf-muted ml-4')
                    return
                with ui.column().classes('w-full gap-0 ml-4'):
                    for n, _, reasons in options:
                        with ui.row().classes('items-center gap-2 no-wrap'):
                            ui.button(src.cards[n].name,
                                      on_click=lambda n=n: (imp.update(swap=num), swap(r, sec, lost, n))) \
                                .props('outline dense no-caps size=sm color=primary')
                            ui.label(f'可放 {min(lost, room(r, n))} 张 · ' + '、'.join(reasons)).classes('text-xs tf-muted')

            def pick(ln, num):
                ln.num = num or 0
                ln.score = 1.0 if num else 0.0
                if num and ln.text:
                    aliases()[ln.text] = num          # remembered for next imports
                    WS.save_config()
                r = imp['res']
                imp['res'] = importer.finish(r.lines, importer.parse(imp['text'])[1], src, trunk=S.trunk)
                result.refresh()

            def apply():
                r = imp['res']
                snapshot()
                if imp['target'] == 'new' and free is not None:
                    st['work'][free] = dict(name=imp['name'] or '导入的卡组', main=[], extra=[], side=[], stamp=None)
                    st['slot'] = free
                d = deck()
                d.update(main=list(r.main), extra=list(r.extra), side=list(r.side))
                if imp['target'] == 'new':
                    d['name'] = imp['name'] or d['name']
                dlg.close()
                refresh_all()
                ui.notify('已导入编辑器。确认没问题后点「保存」写入存档。', type='positive', timeout=6000)

            @ui.refreshable
            def result():
                r = imp['res']
                if r is None:
                    return
                with ui.row().classes('gap-1 mt-2 items-center'):
                    for sec in SECTIONS:
                        ui.chip(f'{SEC_LABEL[sec]} {len(getattr(r, sec))}').props('dense')
                    if r.unresolved:
                        ui.chip(f'未识别 {len(r.unresolved)}', icon='help').props('dense color=red-2 text-color=red-10')
                    else:
                        ui.chip('全部识别', icon='check').props('dense color=green-2 text-color=green-10')
                for msg in r.adjustments:
                    ui.label('↻ ' + msg).classes('text-xs text-blue-400')
                for num, sec, lost, why in r.cuts:
                    swap_row(r, num, sec, lost, why)
                for msg in r.warnings:
                    ui.label('⚠ ' + msg).classes('text-xs text-amber-500')
                with ui.column().classes('w-full gap-1 mt-2'):
                    for ln in r.lines:
                        color = ('green' if ln.num and ln.score >= 0.95 else 'amber' if ln.num else 'red')
                        with ui.row().classes('w-full items-center gap-2 no-wrap'):
                            ui.icon({'green': 'check_circle', 'amber': 'help', 'red': 'error'}[color]) \
                                .classes(f'text-{color}-500')
                            ui.label(f'{SEC_LABEL[ln.section][:2]} ×{ln.count}').classes('text-xs tf-muted w-14 shrink-0')
                            ui.label(ln.text or ln.raw).classes('text-sm w-40 shrink-0 ellipsis overflow-hidden whitespace-nowrap')
                            ui.icon('east').classes('tf-muted shrink-0')
                            options = {0: '（跳过这一行）'}
                            for n, sc in ln.candidates or ([(ln.num, ln.score)] if ln.num else []):
                                c = src.cards.get(n)
                                if c:
                                    tag = '原创 ' if c.game_only else ''
                                    options[n] = f'{c.name}  ·  {tag}{FRAME_NAMES.get(c.frame, "")} #{n}  ({sc:.0%})'
                            if ln.num and ln.num not in options:
                                options[ln.num] = src.cards[ln.num].name
                            ui.select(options, value=ln.num or 0, on_change=lambda e, ln=ln: pick(ln, e.value)) \
                                .props('dense outlined options-dense').classes('flex-1 min-w-0')
                            if ln.note:
                                ui.label(ln.note).classes('text-xs text-red-400')
                ui.separator().classes('my-2')
                with ui.row().classes('w-full items-center gap-2'):
                    opts = {'new': f'新卡组（#{free}）' if free is not None else '新卡组（没有空位）',
                            'replace': f'替换当前卡组 #{st["slot"]}「{deck()["name"]}」'}
                    ui.radio(opts, value=imp['target'], on_change=lambda e: imp.update(target=e.value)).props('inline dense')
                    ui.input('卡组名', value=imp['name'], on_change=lambda e: imp.update(name=e.value)) \
                        .props('dense outlined maxlength=63').classes('w-48')
                with ui.row().classes('w-full justify-end gap-2 mt-2'):
                    if r.unresolved:
                        ui.label(f'还有 {len(r.unresolved)} 行没认出来，会跳过').classes('text-xs text-red-400 self-center')
                    ui.button('导入到编辑器', icon='download_done', on_click=apply) \
                        .props('unelevated color=primary no-caps') \
                        .set_enabled(bool(r.main or r.extra or r.side) and (imp['target'] == 'replace' or free is not None))
            result()
        dlg.open()

    def open_export():
        d = as_deck(deck())
        texts = {'ydk': importer.to_ydk(d, src.cards), 'text': importer.to_text(d, src.cards)}
        state = {'kind': 'text'}
        with ui.dialog() as dlg, ui.card().classes('w-full').style('max-width:640px'):
            ui.label(f'导出「{deck()["name"]}」').classes('text-lg font-bold')

            @ui.refreshable
            def body():
                ui.toggle({'text': '文本', 'ydk': 'YDK'}, value=state['kind'],
                          on_change=lambda e: (state.update(kind=e.value), body.refresh())).props('dense no-caps')
                ui.textarea(value=texts[state['kind']]).props('outlined readonly').classes('w-full') \
                    .style('font-family:monospace')
                if state['kind'] == 'ydk' and '# ' in texts['ydk'].split('#main', 1)[1]:
                    ui.label('游戏原创卡没有卡片密码，在 YDK 里写成注释，其他程序会忽略。').classes('text-xs tf-muted')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('复制', icon='content_copy',
                              on_click=lambda: (ui.clipboard.write(texts[state['kind']]), ui.notify('已复制'))) \
                        .props('unelevated color=primary no-caps')
                    ui.button('关闭', on_click=dlg.close).props('flat no-caps')
            body()
        dlg.open()

    # ---------- deck doctor (on demand only)
    def open_doctor():
        d = as_deck(deck())
        rep = doctor.analyse(d, src.cards)
        cnt = collections.Counter(d.main)
        order = sorted(cnt, key=lambda n: (-cnt[n], view(n).card.name))
        pick = {'group': []}
        pct = lambda p: f'{p:.0%}' if p < 0.995 else '≈100%'
        with ui.dialog() as dlg, ui.card().classes('w-full').style('max-width:680px'):
            ui.label(f'卡组分析「{deck()["name"]}」').classes('text-lg font-bold')
            with ui.tabs().props('dense no-caps align=left').classes('w-full') as tabs:
                t_sum, t_odds, t_adv = ui.tab('概览'), ui.tab('上手率'), ui.tab('建议')
            with ui.tab_panels(tabs, value=t_sum).classes('w-full').style('max-height:62vh;overflow:auto'):
                with ui.tab_panel(t_sum):
                    with ui.row().classes('gap-1'):
                        for label, v, color in (('怪兽', rep.monsters, 'orange'), ('魔法', rep.spells, 'teal'),
                                                ('陷阱', rep.traps, 'pink'), ('未知', rep.unknown, 'grey')):
                            if v or label != '未知':
                                ui.chip(f'{label} {v}').props(f'dense color={color}-1 text-color={color}-9')
                    if rep.by_frame:
                        ui.label('主卡组怪兽').classes('font-semibold mt-2')
                        ui.label('　'.join(f'{FRAME_NAMES.get(k, k)} {v}' for k, v in
                                          sorted(rep.by_frame.items(), key=lambda kv: -kv[1]))).classes('text-sm')
                        if rep.tuners or rep.dark_tuners:
                            ui.label(f'调整 {rep.tuners}' + (f'　黑暗调整 {rep.dark_tuners}' if rep.dark_tuners else '')) \
                                .classes('text-sm')
                    if rep.levels:
                        ui.label('等级分布').classes('font-semibold mt-2')
                        top = max(rep.levels.values())
                        for lv, v in rep.levels.items():
                            with ui.row().classes('items-center gap-2 no-wrap w-full'):
                                ui.label(f'★{lv}').classes('text-xs w-8 text-right')
                                ui.element('div').style(f'height:12px;width:{max(4, 70 * v / top)}%;'
                                                        'background:var(--q-primary);border-radius:3px')
                                ui.label(str(v)).classes('text-xs')
                    if rep.extra_by_frame:
                        ui.label('额外卡组').classes('font-semibold mt-2')
                        ui.label('　'.join(f'{FRAME_NAMES.get(k, k)} {v}' for k, v in rep.extra_by_frame.items())) \
                            .classes('text-sm')
                with ui.tab_panel(t_odds).classes('px-0'):
                    ui.label(f'主卡组 {len(d.main)} 张。下表是至少抽到 1 张的概率；先攻第 1 回合不抽卡，T2/T3 指先攻方的第 2、3 回合。') \
                        .classes('text-xs tf-muted')

                    @ui.refreshable
                    def group_odds():
                        if not pick['group']:
                            ui.label('选几张卡（比如所有启动卡），看抽到其中任意一张的概率。').classes('text-xs tf-muted')
                            return
                        o = doctor.odds(d.main, pick['group'])
                        n = sum(cnt[x] for x in pick['group'])
                        ui.label(f'合计 {n} 张：' + '　'.join(f'{k} {pct(v)}' for k, v in o.items())) \
                            .classes('text-sm font-semibold')

                    ui.select({n: f'{view(n).card.name} ×{cnt[n]}' for n in order}, multiple=True, label='组合',
                              on_change=lambda e: (pick.update(group=e.value or []), group_odds.refresh())) \
                        .props('dense outlined use-chips').classes('w-full')
                    group_odds()
                    rows = []
                    for n in order:
                        o = doctor.odds(d.main, [n])
                        rows.append({'name': view(n).card.name, 'k': cnt[n], **{k: pct(v) for k, v in o.items()}})
                    short = {'先攻起手': '先攻', '后攻起手': '后攻', '先攻第2回合': 'T2', '先攻第3回合': 'T3'}
                    cols = [{'name': 'name', 'label': '卡名', 'field': 'name', 'align': 'left', 'style': 'min-width:7em'},
                            {'name': 'k', 'label': '张', 'field': 'k'}] + \
                           [{'name': k, 'label': short.get(k, k), 'field': k} for k, *_ in doctor.DRAWS]
                    ui.table(columns=cols, rows=rows, row_key='name').props('dense flat wrap-cells') \
                        .classes('w-full mt-2')
                with ui.tab_panel(t_adv):
                    icons = {'warn': ('warning', 'text-amber-600'), 'info': ('info', 'text-blue-500'),
                             'good': ('check_circle', 'text-green-600')}
                    for level, text in rep.advice:
                        with ui.row().classes('items-start gap-2 no-wrap mb-2'):
                            ui.icon(icons[level][0]).classes(icons[level][1])
                            ui.label(text).classes('text-sm')
                    ui.label('以上只是一般经验，具体还要看卡组怎么打。').classes('text-xs tf-muted mt-2')
            with ui.row().classes('w-full justify-end'):
                ui.button('关闭', on_click=dlg.close).props('flat no-caps')
        dlg.open()

    # ---------- deck catalog
    def open_catalog():
        cat = dict(query='', group=None, champion=False, limit=60, entry=None, target='new', busy=False, mode='local',
                   fit=True)
        free = next((i for i in range(NSLOTS) if i not in st['work']), None)
        imp = dict(text='', name='')
        by_pc = {**ygoprodeck.passcode_index(src.cards, importer.standins(src.cards)), **WS.passcodes.extra_index(src.cards)}
        limit = (lambda n: (S.trunk(n) or (3, 3))[1]) if src.has_trunk and S.save else None
        data = {}

        def reload_local():
            data['all'] = deckcatalog.entries(src, S.game.short, WS.wiki, WS.names_db(), aliases(),
                                              saved=WS.ygopro.load(), codes=WS.passcodes.extra_index(src.cards),
                                              mine=WS.library.load(S.game.short))

        reload_local()

        def shown():
            q = search_key(cat['query'])
            out = []
            for e in data['all']:
                if cat['group'] and e.group != cat['group'] or cat['champion'] and not e.champion:
                    continue
                if q and q not in search_key(f'{e.name} {e.character}'):
                    continue
                out.append(e)
            return out

        def short_of(d):
            """Copies the collection lacks for this deck (None when the trunk is not mapped)."""
            if not d['main'] or S.trunk(d['main'][0]) is None:
                return None
            need = collections.Counter(d['main'] + d['extra'] + d['side'])
            return sum(max(0, k - (S.trunk(n) or (0, 0))[0]) for n, k in need.items())

        def cap_of(n):
            """Copies this game's ban list allows (owned counts are left to the 收藏缺 chip)."""
            t = S.trunk(n)
            return min(3, t[1]) if t else 3

        def aligned(e):
            """(fitted deck, cuts, picks) for e under this game's ban list, cached per entry and setting."""
            key = (e.key, S.banlist, id(S.save))
            a = cat.get('align')
            if not a or a[0] != key:
                fitted, cuts = similar.align({s: getattr(e, s) for s in SECTIONS}, src.cards, cap_of,
                                             ok=lambda n: view(n).addable)
                picks = similar.suggest(cuts, cap_of, collections.Counter(fitted['main'] + fitted['extra']))
                cat['align'] = a = (key, fitted, cuts, picks)
            return a[1:]

        def final(e):
            """The deck 载入 will put in the editor: as listed, or fitted to the ban list with the picked swaps."""
            fitted, cuts, picks = aligned(e)
            if cuts and cat['fit']:
                return similar.fill(fitted, cuts, picks, cap_of)
            return {s: list(getattr(e, s)) for s in SECTIONS}

        def load(e):
            d = final(e)
            snapshot()
            if cat['target'] == 'new':
                st['work'][free] = dict(name='', main=[], extra=[], side=[], stamp=None)
                st['slot'] = free
            deck().update(name=e.name[:63], main=d['main'], extra=d['extra'], side=d['side'])
            dlg.close()
            refresh_all()
            ui.notify(f'已载入「{e.name}」。确认没问题后点「保存」写入存档。', type='positive', timeout=6000)

        async def download():
            cat['busy'] = True
            body.refresh()
            try:
                if not WS.names_db():
                    ui.notify('先下载卡名库，要用英文卡名来对应卡片…')
                    await run.io_bound(WS.download_names)
                n = len(await run.io_bound(WS.wiki.download, S.game.short))
                reload_local()
                ui.notify(f'已下载 {n} 个角色页面', type='positive')
            except OSError as ex:
                ui.notify(f'下载失败：{ex}', type='negative')
            cat['busy'] = False
            body.refresh()

        def deck_list(d):
            for sec in SECTIONS:
                cnt = collections.Counter(d[sec])
                if not cnt:
                    continue
                ui.label(f'{SEC_LABEL[sec]} {sum(cnt.values())}').classes('font-semibold mt-2')
                order = sorted(cnt, key=lambda n: ({'spell': 1, 'trap': 2}.get(view(n).card.frame, 0), -view(n).card.level, n))
                with ui.element('div').classes('tf-grid'):
                    for n in order:
                        card_tile(view(n), count=cnt[n], on_click=lambda n=n: select(n))

        def fit_view(e):
            """Cards over this game's ban list, each with a swap picked from cards of similar effect."""
            fitted, cuts, picks = aligned(e)
            if not cuts:
                return
            lost = sum(k for _, _, k, _ in cuts)
            with ui.row().classes('w-full items-center gap-2 mt-1'):
                ui.switch(f'按本游戏禁限卡表调整（多出 {lost} 张）', value=cat['fit'],
                          on_change=lambda ev: (cat.update(fit=ev.value), body.refresh())).props('dense')
                ui.label('关掉就原样载入').classes('text-xs tf-muted')
            if not cat['fit']:
                return
            ui.label('多出的几张会删掉，换成效果相近、没超限的卡。已经帮你选好，也可以自己换。') \
                .classes('text-xs tf-muted')

            def choose(key, value):
                picks[key] = value or 0
                body.refresh()

            with ui.column().classes('w-full gap-1 mt-1'):
                for n, sec, k, options in cuts:
                    c = cap_of(n)
                    why = '禁止卡' if c == 0 else f'限制 {c} 张' if c < 3 else '最多 3 张'
                    with ui.row().classes('w-full items-center gap-2 no-wrap'):
                        ui.label(f'「{src.cards[n].name}」×{k}（{why}）').classes('text-xs w-48 shrink-0')
                        ui.icon('east').classes('tf-muted shrink-0')
                        opts = {0: '只删掉，不补'}
                        opts.update({o: f'{src.cards[o].name} · {"、".join(r[:2])}' for o, _, r in options})
                        ui.select(opts, value=picks.get((n, sec), 0),
                                  on_change=lambda ev, key=(n, sec): choose(key, ev.value)) \
                            .props('dense outlined options-dense').classes('flex-1 min-w-0')

        def preview(e):
            with ui.row().classes('items-center gap-2 no-wrap w-full'):
                ui.button(icon='arrow_back', on_click=lambda: (cat.update(entry=None, raw=None), body.refresh())) \
                    .props('flat round dense')
                with ui.column().classes('gap-0 min-w-0'):
                    ui.label(e.name).classes('text-lg font-bold')
                    ui.label(' · '.join(x for x in (e.character, e.level_label, e.group) if x)).classes('text-xs tf-muted')
            d = final(e)
            issues = [problem_zh(m) for m in S.problems(Deck(e.name, d['main'], d['extra'], d['side']))]
            lack = short_of(d)
            with ui.row().classes('gap-1 mt-1'):
                for sec in SECTIONS:
                    ui.chip(f'{SEC_LABEL[sec]} {len(d[sec])}').props('dense')
                if not issues:
                    ui.chip('合规', icon='verified').props('dense color=blue-1 text-color=blue-9')
                if lack:
                    ui.chip(f'收藏缺 {lack} 张', icon='inventory_2').props('dense color=amber-2 text-color=amber-10')
            for msg in issues[:4]:
                ui.label('⚠ ' + msg).classes('text-xs text-red-500')
            if e.missing:
                ui.label(f'本游戏没有这些卡，已跳过：{"、".join(e.missing)}').classes('text-xs text-amber-500 mt-1')
            fit_view(e)
            if e.key.startswith('my:'):
                ui.button('从我的卡组删除', icon='delete', on_click=lambda: forget(e)) \
                    .props('flat dense no-caps size=sm color=grey-7')
            raw = cat.get('raw')
            if e.url or raw:
                with ui.row().classes('items-center gap-2'):
                    if e.url:
                        ui.link(f'来源：{e.source}', e.url, new_tab=True).classes('text-xs')
                    if raw and e.key.startswith('ygopro:'):
                        text, color = fit_note(raw)
                        ui.label(text).classes(f'text-xs {color}')
                        if WS.ygopro.has(raw):
                            ui.button('已保存 · 移除', icon='bookmark_remove', on_click=lambda: toggle_saved(raw)) \
                                .props('flat dense no-caps size=sm color=grey-7')
                        else:
                            ui.button('保存到卡组库', icon='bookmark_add', on_click=lambda: toggle_saved(raw)) \
                                .props('unelevated dense no-caps size=sm color=primary')
            with ui.element('div').classes('w-full shrink-0').style('max-height:48vh;overflow:auto') \
                    .props(f'data-keep=catdeck-{e.key}'):
                deck_list(d)
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                opts = {'new': f'新卡组（#{free}）' if free is not None else '新卡组（没有空位）',
                        'replace': f'替换当前卡组 #{st["slot"]}「{deck()["name"]}」'}
                ui.radio(opts, value=cat['target'], on_change=lambda ev: cat.update(target=ev.value)).props('inline dense')
                ui.space()
                ui.button('载入到编辑器', icon='download_done', on_click=lambda: load(e)) \
                    .props('unelevated color=primary no-caps') \
                    .set_enabled(cat['target'] == 'replace' or free is not None)

        def forget(e):
            with ui.dialog() as ask, ui.card():
                ui.label(f'从我的卡组删除「{e.name}」？').classes('font-bold')
                ui.label('只删电脑上存的这一份，存档里的卡组不受影响。').classes('text-sm tf-muted')

                def go():
                    WS.library.remove(e.key[3:])
                    ask.close()
                    reload_local()
                    cat.update(entry=None, raw=None)
                    body.refresh()
                    ui.notify(f'已删除「{e.name}」')

                with ui.row().classes('w-full justify-end'):
                    ui.button('取消', on_click=ask.close).props('flat no-caps')
                    ui.button('删除', on_click=go).props('unelevated color=negative no-caps')
            ask.open()

        def toggle_saved(raw):
            if WS.ygopro.has(raw):
                WS.ygopro.remove(raw['id'])
                ui.notify(f'已从卡组库移除「{raw["name"]}」')
            else:
                WS.ygopro.add(raw)
                ui.notify(f'已保存「{raw["name"]}」到卡组库，TF6 和 TFSP 都能用', type='positive')
            reload_local()
            body.refresh()

        def open_entry(e, raw=None):
            cat.update(entry=e, raw=raw)
            body.refresh()

        def open_local(e):
            raw = next((d for d in WS.ygopro.load() if f"ygopro:{d['id']}" == e.key), None)
            open_entry(e, raw)

        async def check_ydk():
            raw = ygoprodeck.from_ydk(imp['text'], imp['name'])
            if raw is None:
                ui.notify('没读到卡片。请粘贴 YDK 文件内容（以 #main 开头）或 ydke:// 链接', type='warning')
                return
            by_pc.update(await resolve_passcodes(imp['text']))
            open_entry(deckcatalog.from_ygoprodeck([raw], src.cards, WS.names_db(), codes=by_pc)[0], raw)

        async def ydk_file(ev):
            imp.update(text=await ev.file.text(), name=os.path.splitext(ev.file.name)[0])
            await check_ydk()

        def fit_note(raw):
            f = ygoprodeck.fit(raw, by_pc, limit)
            if not f['changes']:
                return '完全适配本游戏', 'text-green-600'
            bits = ([f"本游戏没有 {len(f['missing'])} 张"] if f['missing'] else []) + \
                   ([f"超出禁限卡表 {sum(k - a for _, k, a in f['over'])} 张"] if f['over'] else [])
            return '，'.join(bits), 'text-amber-600'

        def web_view():
            ui.label(f'在 YGOPRODeck 找适合 {S.game.short} 的卡组').classes('font-semibold')
            ui.label('Tag Force 的卡池基本跟着 OCG 走，同一时期的真实卡组大多能直接用。'
                     '点下面的链接，会在浏览器里打开网站的卡组搜索，条件已经填好。').classes('text-xs tf-muted')
            with ui.column().classes('w-full gap-1 mt-1'):
                for label, category, name, hint in ygoprodeck.SEARCHES.get(S.game.short, []):
                    with ui.row().classes('items-center gap-2 no-wrap'):
                        ui.link(label, ygoprodeck.search_url(category, name), new_tab=True).classes('text-sm shrink-0')
                        ui.label(hint).classes('text-xs tf-muted')
            ui.label('步骤').classes('font-semibold mt-3')
            for i, step in enumerate(('在网站上打开一个卡组，点「More...」→「Download YDK」下载 .ydk 文件，或点「YDKE」复制链接。',
                                      '回到这里选择 .ydk 文件，或把内容粘贴进来，然后点「检查」。',
                                      '预览里会列出本游戏没有的卡；超出禁限卡表的会换成效果相近的卡，可以自己改。'
                                      '可以直接载入编辑器，也可以「保存到卡组库」留着以后用，两个游戏都能用。'), 1):
                ui.label(f'{i}. {step}').classes('text-xs')
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                ui.upload(label='选择 .ydk 文件', auto_upload=True, on_upload=ydk_file) \
                    .props('accept=.ydk,.txt flat bordered dense').classes('w-56')
                with ui.column().classes('flex-1 min-w-[12em] gap-1'):
                    ui.input('卡组名', value=imp['name'], on_change=lambda ev: imp.update(name=ev.value or '')) \
                        .props('dense outlined maxlength=63')
            ui.textarea(placeholder='#main\n97268402\n…\n#extra\n…\n!side\n…    或 ydke://…', value=imp['text'],
                        on_change=lambda ev: imp.update(text=ev.value or '')).props('outlined rows=5').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('检查', icon='fact_check', on_click=check_ydk).props('unelevated color=primary no-caps')

        def listing():
            ui.toggle({'local': '卡组库', 'web': f'从 {ygoprodeck.SOURCE} 导入'}, value=cat['mode'],
                      on_change=lambda ev: (cat.update(mode=ev.value), body.refresh())) \
                .props('dense no-caps rounded unelevated toggle-color=primary').classes('mb-1')
            if cat['mode'] == 'web':
                web_view()
                return
            groups = sorted({e.group for e in data['all']}, key=[e.group for e in data['all']].index)
            with ui.row().classes('w-full items-center gap-2'):
                ui.input(placeholder='搜索卡组名 / 角色', value=cat['query'],
                         on_change=lambda ev: (cat.update(query=ev.value or '', limit=60), rows.refresh())) \
                    .props('dense outlined clearable debounce=250').classes('flex-1 min-w-[10em]')   # clear → None
                ui.select({None: '全部分类', **{g: g for g in groups}}, value=cat['group'],
                          on_change=lambda ev: (cat.update(group=ev.value, limit=60), rows.refresh())) \
                    .props('dense outlined options-dense').classes('w-36')
                ui.switch('冠军级', value=cat['champion'],
                          on_change=lambda ev: (cat.update(champion=ev.value, limit=60), rows.refresh())) \
                    .tooltip('WCS 冠军卡组、认真卡组和每个角色最强的一套（Lv4）；网上的卡组看 9★ 以上的')
            if WS.wiki.supported(S.game.short):
                with ui.row().classes('w-full items-center gap-2 text-xs tf-muted'):
                    if WS.wiki.has(S.game.short):
                        ui.label(f'已包含 {wikidecks.SOURCE} 上的角色卡组（按英文卡名对应）')
                        ui.button('重新下载', icon='refresh', on_click=download).props('flat dense no-caps size=sm') \
                            .set_enabled(not cat['busy'])
                    else:
                        ui.label(f'本游戏的 ISO 里读不到卡组配方，可以从 {wikidecks.SOURCE} 下载角色卡组（约 130 页）。')
                        ui.button('下载', icon='cloud_download', on_click=download).props('unelevated dense no-caps color=primary') \
                            .set_enabled(not cat['busy'])
                    if cat['busy']:
                        ui.spinner(size='sm')
            rows()

        @ui.refreshable
        def rows():
            res = shown()
            ui.label(f'{len(res)} 套卡组').classes('text-xs tf-muted mt-1')
            if not data['all']:
                ui.label('还没有卡组。TFSP 要先添加 ISO，TF6 要先下载网上的卡组。').classes('tf-muted p-4')
            with ui.column().classes('w-full gap-0').style('max-height:60vh;overflow:auto'):
                for e in res[:cat['limit']]:
                    with ui.element('div').classes('tf-slot w-full').on('click', lambda e=e: open_local(e)):
                        with ui.row().classes('items-center gap-1 no-wrap'):
                            if e.champion:
                                ui.icon('emoji_events').classes('text-amber-500 text-sm')
                            ui.label(e.name).classes('font-semibold ellipsis overflow-hidden whitespace-nowrap')
                            if e.missing:
                                ui.icon('report').classes('text-amber-500 text-sm').tooltip(f'缺 {len(e.missing)} 种卡')
                        meta = [x for x in (e.character, e.level_label, e.group) if x]
                        ui.label(' · '.join(meta) + f' · {len(e.main)}/{len(e.extra)}/{len(e.side)}') \
                            .classes('text-xs tf-muted')
                if len(res) > cat['limit']:
                    ui.button('加载更多', on_click=lambda: (cat.update(limit=cat['limit'] + 60), rows.refresh())) \
                        .props('flat color=primary').classes('w-full mt-1')

        with ui.dialog().props('maximized-mobile') as dlg, \
                ui.card().classes('w-full').style('max-width:760px; max-height:92dvh; overflow:auto'):
            with ui.row().classes('w-full items-center'):
                ui.label('卡组库').classes('text-lg font-bold')
                ui.space()
                ui.button(icon='close', on_click=dlg.close).props('flat round dense')

            @ui.refreshable
            def body():
                if cat['entry']:
                    preview(cat['entry'])
                else:
                    listing()
            body()
        dlg.open()

    # ---------- save
    def review():
        changed = [i for i in sorted(st['work']) if dirty(i)]
        blocked = False
        with ui.context.client.content, ui.dialog() as dlg, ui.card().classes('min-w-[320px] max-w-[560px]'):
            ui.label('写入存档前确认').classes('text-lg font-bold')
            ui.label(S.folder.path).classes('tf-muted text-xs')
            for i in changed:
                w, o = st['work'][i], st['orig'].get(i)
                ui.label(f"#{i} {w['name']}" + ('（新卡组）' if o is None else '')).classes('font-semibold mt-2')
                if o and o['name'] != w['name']:
                    ui.label(f"改名：{o['name']} → {w['name']}").classes('text-sm')
                for sec in SECTIONS:
                    a = collections.Counter(o[sec] if o else [])
                    b = collections.Counter(w[sec])
                    for n in sorted(set(a) | set(b)):
                        if a[n] != b[n]:
                            color = 'text-green-600' if b[n] > a[n] else 'text-red-500'
                            ui.label(f'{SEC_LABEL[sec]} · {view(n).card.name}: {a[n]} → {b[n]}').classes(f'text-sm {color}')
                for msg in map(problem_zh, S.problems(as_deck(w))):
                    blocked = True
                    ui.label('⚠ ' + msg).classes('text-sm text-red-500')
            ui.label('写入前会先备份整个存档文件夹，写入后再读一遍校验。').classes('text-xs tf-muted mt-3')
            if S.dev:
                ui.label(f'然后写回掌机 {S.device_meta["host"]}：先确认没有游戏在运行、存档没被游戏改过，'
                         f'在掌机上备份后再写入并校验。').classes('text-xs text-purple-400')
            if blocked:
                ui.label('有卡组不合规，改好后才能保存。').classes('text-sm text-red-500')
            with ui.row().classes('w-full justify-end'):
                ui.button('取消', on_click=dlg.close).props('flat')
                ui.button('写入存档', icon='save', on_click=lambda: commit(dlg, changed)) \
                    .props('unelevated color=primary no-caps').set_enabled(not blocked)
        dlg.open()

    async def commit(dlg, changed):
        client = ui.context.client
        dlg.close()
        try:
            backup = S.commit({i: as_deck(st['work'][i]) for i in changed})
        except SaveChanged:
            with client:
                ui.notify('打开之后，存档又被游戏改过。请回首页重新打开，再改一次。', type='negative', multi_line=True, timeout=0,
                          close_button='知道了')
            return
        except Exception as e:     # nothing was written if encode/verify failed; say so
            with client:
                ui.notify(f'写入失败，存档没有改动：{e}', type='negative', multi_line=True, timeout=0, close_button='知道了')
            return
        st['orig'] = originals()
        st['work'] = {i: dict(d, main=list(d['main']), extra=list(d['extra']), side=list(d['side'])) for i, d in st['orig'].items()}
        st['history'] = []
        if not S.dev:
            refresh_all()
            with client:
                ui.notify(f'已写入存档。备份：{backup}', type='positive', multi_line=True, timeout=8000)
            return
        st['push_pending'] = True
        save_button.refresh()
        await push(client)

    async def push(client=None):
        client = client or ui.context.client
        with client:
            n = ui.notification(f'正在写回掌机 {S.device_meta["host"]}…', spinner=True, timeout=None)
        try:
            remote_backup = await run.io_bound(S.push)
        except device.GameRunning:
            with client:
                ui.notify('掌机正在运行游戏，所以没有写回。请在掌机上退回主菜单，再点「写回掌机」。改动已存在电脑上。',
                          type='warning', multi_line=True, timeout=0, close_button='知道了')
        except device.RemoteChanged:
            with client:
                ui.notify('读取之后，掌机上的存档又被游戏改过。为了不覆盖游戏进度，这次没有写回。请回首页重新读取，再改一次。',
                          type='negative', multi_line=True, timeout=0, close_button='知道了')
        except Exception as e:     # network down, key refused, verify mismatch (backup kept on device)
            with client:
                ui.notify(f'写回掌机失败：{e}', type='negative', multi_line=True, timeout=0, close_button='知道了')
        else:
            st['push_pending'] = False
            with client:
                ui.notify(f'已写入存档并写回掌机。掌机上的备份：{remote_backup}', type='positive', multi_line=True, timeout=10000)
        finally:
            n.dismiss()
        refresh_all()

    @ui.refreshable
    def detail():
        with ui.element('div').classes('tf-scroll'):
            detail_content()

    @ui.refreshable
    def panels():
        with ui.element('div').classes('tf-layout'):
            with ui.element('div').classes('tf-panel' + ('' if st['tab'] == 'cards' else ' tf-inactive')):
                with ui.column().classes('gap-2 p-3 w-full'):
                    with ui.row().classes('w-full no-wrap items-center gap-2'):
                        ui.input(placeholder='搜索卡名（中/日/英）、编号或密码…', value=st['query'],
                                 on_change=lambda e: (st.update(query=e.value or '', limit=120), browser_grid.refresh())) \
                            .props('outlined dense clearable rounded debounce=150').classes('flex-1') \
                            .add_slot('prepend', '<q-icon name="search" />')
                        ui.button('多选', icon='checklist', on_click=lambda: (toggle_multi('cards'), panels.refresh())) \
                            .props(f"{'unelevated color=amber-7 text-color=black' if st['multi_cards'] else 'outline'} no-caps")
                    with ui.row().classes('items-center gap-2 w-full'):
                        ui.toggle({'all': '全部', 'monster': '怪兽', 'SPELL': '魔法', 'TRAP': '陷阱'}, value=st['kind'],
                                  on_change=lambda e: (st.update(kind=e.value, limit=120), browser_grid.refresh())) \
                            .props('dense no-caps rounded unelevated toggle-color=primary')
                        ui.select({None: '属性', **{k: v[0] for k, v in ATTR.items() if k not in ('SPELL', 'TRAP', '?')}},
                                  value=st['attr'], on_change=lambda e: (st.update(attr=e.value, limit=120), browser_grid.refresh())) \
                            .props('dense outlined options-dense').classes('w-24')
                        ui.select({None: '星级', **{k: label for k, (label, _) in STARS.items()}},
                                  value=st['stars'], on_change=lambda e: (st.update(stars=e.value, limit=120), browser_grid.refresh())) \
                            .props('dense outlined options-dense').classes('w-28').tooltip('超量怪兽按阶级算')
                        if src.has_trunk:
                            ui.switch('只看已持有', value=st['owned_only'],
                                      on_change=lambda e: (st.update(owned_only=e.value), browser_grid.refresh())).props('dense')
                    tag_chips()
                with ui.element('div').classes('tf-scroll').props('data-keep=cards'):
                    browser_grid()
            with ui.element('div').classes('tf-panel' + ('' if st['tab'] == 'deck' else ' tf-inactive')):
                deck_view()
            with ui.element('div').classes('tf-panel tf-detail-panel'):
                detail()

    if src.kind != 'iso':
        ui.label({'names': '没有 ISO：卡片只显示文字（卡名来自卡名库），没有卡图；卡片列表、持有数和禁限卡取自存档。',
                  'numbers': '没有 ISO，也没有卡名库，只能显示卡片编号。请在首页添加 ISO 或下载卡名库。'}[src.kind]) \
            .classes('w-full text-center text-sm bg-amber-200 text-black rounded p-1')
    panels()


def _unknown(n):
    from tfcore.carddb import Card
    return Card(n, 0, 0, f'#{n}', '', '?', 'effect', 0, 0, 0, arts=0)


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(title='TF Deck Studio', host='0.0.0.0', port=ARGS.port, reload=False,
           show=False, dark=True, favicon='🃏')
