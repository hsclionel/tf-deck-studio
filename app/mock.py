"""Clickable design mock for the TF deck editor (NiceGUI). Read-only: edits live in memory.

  .venv/Scripts/python app/mock.py          -> http://localhost:8080 (also on the LAN)

All data comes the way the real app gets it: a catalog built from the user's ISO
(`python -m tfcore.cli catalog <iso> --cache testdata/cache`) and the save folder in
testdata/memstick, opened with tfcore.
"""
import collections, html, pathlib, re, sys, unicodedata

from nicegui import app, ui

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tfcore.catalog import Catalog  # noqa: E402
from tfcore.savefolder import SaveFolder  # noqa: E402
from tfcore.tf6save import NSLOTS, TF6Save  # noqa: E402

CATALOG = next((ROOT / 'testdata/cache').glob('ULJM05940-*'))
SAVE_DIR = ROOT / 'testdata/memstick/PSP/SAVEDATA/ULJM059400001'
app.add_static_files('/art', CATALOG / 'art')

# ---------------------------------------------------------------- data

ATTR = {'LIGHT': ('光', '#e8b923'), 'DARK': ('暗', '#7b5ea7'), 'WATER': ('水', '#3d8fd6'),
        'FIRE': ('炎', '#e4572e'), 'EARTH': ('地', '#8d6236'), 'WIND': ('风', '#3fa363'),
        'DIVINE': ('神', '#c99a1c'), 'Spell': ('魔', '#1f9e89'), 'Trap': ('罠', '#b44f8a')}
FRAME_LABEL = {'normal': '通常', 'effect': '效果', 'fusion': '融合', 'synchro': '同调', 'xyz': '超量',
               'ritual': '仪式', 'pendulum': '灵摆', 'token': '衍生物', 'spell': '魔法卡', 'trap': '陷阱卡'}
EXTRA_FRAMES = ('fusion', 'synchro', 'xyz')


def search_key(s):
    """Full-width → half-width, lower case, separators dropped: 'Ｅ·ＨＥＲＯ　天空侠' → 'ehero天空侠'."""
    return re.sub(r'[\s·・\-－_.,，。!！]', '', unicodedata.normalize('NFKC', s)).lower()


def load_data():
    cat = Catalog(str(CATALOG))
    save = TF6Save(SaveFolder(SAVE_DIR).plain)
    used = {i: dict(name=d.name, main=d.main, extra=d.extra, side=d.side, ts=d.stamp)
            for i, d in save.decks().items()}
    cards = {}
    for c in cat.cards.values():
        owned, allowed, _ = save.trunk(c.row)
        cards[c.num] = dict(num=c.num, row=c.row, pas=c.passcode,
                            kind={'SPELL': 'Spell', 'TRAP': 'Trap'}.get(c.attribute, c.attribute),
                            atk=c.atk, dfn=c.defense, level=c.level, name=c.name.replace('　', ' '),
                            frame=c.frame, arts=c.arts, owned=owned, allowed=allowed,
                            key=search_key(c.name), text=c.text)
    return cards, used


CARDS, SLOTS = load_data()
ORDER = sorted(CARDS.values(), key=lambda c: c['num'])
SECTIONS = ('main', 'extra', 'side')

TEXT = {
    'zh': dict(cards='卡片', deck='卡组', search='搜索卡名或编号…', all='全部', monster='怪兽',
               spell='魔法', trap='陷阱', attr='属性', owned_only='只看已拥有', results='张', more='加载更多',
               main='主卡组', extra='额外卡组', side='副卡组', slots='我的卡组', new_deck='新建卡组',
               partner='伙伴卡组（只读）', push='检查并推送', import_='导入文本', export='导出 YDK', undo='撤销',
               add_main='加入主卡组', add_extra='加入额外卡组', add_side='加入副卡组', remove='移除一张',
               owned='拥有', limit='限制', alt='卡图', used_in='使用于', empty='点选一张卡片查看详情',
               mock='设计模型 · 不写入存档', diff_title='将要写入设备的改动', no_change='没有改动',
               confirm='推送（模型中不执行）', cancel='取消', passcode='密码', number='编号', ok='合规',
               multi='多选', picked='已选', clear='取消选择', to_main='移到主卡组', to_extra='移到额外',
               to_side='移到副卡组', delete='移除', kinds='种'),
    'en': dict(cards='Cards', deck='Deck', search='Search name or number…', all='All',
               monster='Monster', spell='Spell', trap='Trap', attr='Attribute', owned_only='Owned only',
               results='cards', more='Load more', main='Main', extra='Extra', side='Side', slots='My decks',
               new_deck='New deck', partner='Partner decks (read-only)', push='Review & push', import_='Import text',
               export='Export YDK', undo='Undo', add_main='Add to Main', add_extra='Add to Extra',
               add_side='Add to Side', remove='Remove one', owned='Owned', limit='Limit', alt='Artwork',
               used_in='Used in', empty='Tap a card to see details', mock='Design mock · never writes the save',
               diff_title='Changes that would be written', no_change='No changes', confirm='Push (disabled in mock)',
               cancel='Cancel', passcode='Passcode', number='No.', ok='Legal', multi='Select',
               picked='Selected', clear='Clear', to_main='Move to Main', to_extra='Move to Extra',
               to_side='Move to Side', delete='Remove', kinds='kinds'),
}

CSS = r"""
:root { --tf-bg:#f4f5f7; --tf-panel:#ffffff; --tf-line:#e3e5ea; --tf-muted:#6b7280; }
body.body--dark { --tf-bg:#121417; --tf-panel:#1b1e23; --tf-line:#2b3038; --tf-muted:#9aa3ae; }
body { background:var(--tf-bg); }
.tf-layout { display:grid; gap:12px; grid-template-columns:1fr; width:100%; }
.tf-panel { background:var(--tf-panel); border:1px solid var(--tf-line); border-radius:14px;
            display:flex; flex-direction:column; min-width:0; overflow:hidden; }
.tf-scroll { overflow:auto; min-height:0; flex:1; padding:10px; }
.tf-grid { display:grid; gap:10px; grid-template-columns:repeat(auto-fill, minmax(92px, 1fr)); }
.tf-muted { color:var(--tf-muted); }
@media (min-width:1024px) {
  .tf-layout { grid-template-columns:minmax(0,1.1fr) minmax(0,1fr) 360px; height:calc(100dvh - 92px); }
  .tf-mobile-only { display:none !important; }
}
@media (max-width:1023px) {
  .tf-panel.tf-inactive, .tf-detail-panel { display:none !important; }
  .tf-panel { min-height:calc(100dvh - 160px); overflow:visible; }
  .tf-actions { position:sticky; bottom:56px; z-index:2; background:var(--tf-panel);
                border-radius:0 0 14px 14px; box-shadow:0 -6px 12px rgba(0,0,0,.18); }
  .tf-grid { grid-template-columns:repeat(auto-fill, minmax(76px, 1fr)); gap:8px; }
  .tf-desktop-only { display:none !important; }
  .tf-quick { display:none !important; }
}

/* grid tile */
.tf-card { position:relative; border-radius:7px; padding:4px; cursor:pointer; user-select:none;
           box-shadow:0 1px 3px rgba(0,0,0,.25); transition:transform .12s ease, box-shadow .12s ease; }
.tf-card:hover { transform:translateY(-2px); box-shadow:0 6px 14px rgba(0,0,0,.28); }
.tf-card.sel { outline:3px solid #3b82f6; outline-offset:1px; }
.tf-card.picked { outline:3px solid #f59e0b; outline-offset:1px; }
.tf-hit { display:flex; flex-direction:column; gap:3px; }
.tf-effect { background:linear-gradient(160deg,#d9925a,#b4682f); }
.tf-xyz { background:linear-gradient(160deg,#4b4f57,#25282d); }
.tf-xyz .tf-foot, .tf-xyz .tf-name { background:rgba(255,255,255,.92); }
.tf-pendulum { background:linear-gradient(180deg,#d9925a 0%,#d9925a 55%,#35b29c 100%); }
.tf-normal { background:linear-gradient(160deg,#e9cf7a,#c9a640); }
.tf-ritual { background:linear-gradient(160deg,#7aa6e0,#4775b8); }
.tf-token { background:linear-gradient(160deg,#b8bcc4,#8c919a); }
.tf-fusion { background:linear-gradient(160deg,#a477c9,#7a4ea3); }
.tf-synchro { background:linear-gradient(160deg,#f3f3f3,#cfd3d8); }
.tf-spell { background:linear-gradient(160deg,#35b29c,#1d8574); }
.tf-trap { background:linear-gradient(160deg,#cc6aa3,#9c3f77); }
.tf-name { background:rgba(255,255,255,.9); color:#16181c; border-radius:3px; font-size:10px; line-height:12px;
           padding:2px 3px; font-weight:600; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
           overflow:hidden; height:28px; }
.tf-artimg { width:100%; aspect-ratio:1; object-fit:cover; display:block; border-radius:2px;
             border:1px solid rgba(0,0,0,.35); background:#222; }
.tf-foot { font-size:9px; line-height:12px; color:#16181c; background:rgba(255,255,255,.8); border-radius:3px;
           padding:0 3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tf-badge { position:absolute; font-size:10px; font-weight:700; border-radius:9px; padding:0 6px; line-height:17px; z-index:1; }
.tf-count { top:-7px; right:-7px; background:#2563eb; color:#fff; box-shadow:0 1px 3px rgba(0,0,0,.4); }
.tf-limit { top:36px; left:-5px; background:#dc2626; color:#fff; }
.tf-alt { top:36px; right:-5px; background:#111827; color:#fde68a; }
.tf-check { top:-7px; left:-7px; background:#f59e0b; color:#111; }
.tf-adot { position:absolute; top:36px; left:50%; transform:translateX(-50%); display:none; }
.tf-quick { position:absolute; left:4px; right:4px; bottom:18px; display:none; gap:4px; justify-content:center; z-index:2; }
.tf-card:hover .tf-quick { display:flex; }
.tf-qbtn { flex:1; height:30px; border-radius:6px; border:none; font-size:18px; font-weight:800; cursor:pointer;
           color:#fff; box-shadow:0 2px 6px rgba(0,0,0,.4); }
.tf-qbtn.minus { background:#dc2626; } .tf-qbtn.plus { background:#2563eb; }

/* full card in the detail view */
.tf-real { border-radius:10px; padding:10px; color:#16181c; box-shadow:0 4px 18px rgba(0,0,0,.35); }
.tf-real-name { display:flex; align-items:center; gap:6px; background:rgba(255,255,255,.9); border-radius:4px;
                padding:4px 6px; font-weight:800; font-size:16px; line-height:20px; }
.tf-real-name span:first-child { flex:1; }
.tf-adot2 { width:26px; height:26px; border-radius:50%; color:#fff; font-size:14px; font-weight:800; display:flex;
            align-items:center; justify-content:center; border:2px solid rgba(255,255,255,.8); flex:none; }
.tf-real-stars { text-align:right; color:#c0392b; font-size:15px; letter-spacing:1px; min-height:20px; padding:2px 4px;
                 text-shadow:0 0 2px #fff; }
.tf-real-art { width:86%; margin:2px auto 8px; aspect-ratio:1; display:block; border:2px solid rgba(0,0,0,.45);
               background:#222; image-rendering:auto; }
.tf-real-text { background:rgba(255,255,255,.92); border-radius:4px; padding:6px 8px; font-size:13px; line-height:19px;
                white-space:pre-wrap; max-height:220px; overflow:auto; }
.tf-real-type { font-weight:800; font-size:12px; margin-bottom:2px; }
.tf-real-atk { text-align:right; font-weight:800; font-size:13px; padding:4px 4px 0; }
.tf-big-btn { min-height:46px; font-size:15px !important; }

.tf-section-title { font-weight:700; font-size:13px; display:flex; align-items:center; gap:8px; margin:6px 2px; }
.tf-slot { border-radius:10px; padding:8px 10px; cursor:pointer; border:1px solid transparent; }
.tf-slot:hover { background:rgba(127,127,127,.08); }
.tf-slot.active { border-color:#3b82f6; background:rgba(59,130,246,.10); }
.tf-tab { border-top:3px solid transparent; }
.tf-tab-on { border-top-color:#fbbf24; background:rgba(251,191,36,.12); font-weight:700; }
.tf-pickbar { background:#f59e0b; color:#111; border-radius:12px; margin:6px 8px; padding:6px 8px; }
"""


def foot_text(c):
    if c['kind'] in ('Spell', 'Trap'):
        return FRAME_LABEL[c['frame']]
    return f"{'★' * min(c['level'], 12)} {c['atk']}/{c['dfn']}"


def card_tile(c, count=0, selected=False, picked=False, on_click=None, on_plus=None, on_minus=None):
    classes = f"tf-card tf-{c['frame']}" + (' sel' if selected else '') + (' picked' if picked else '')
    with ui.element('div').classes(classes) as tile:
        with ui.element('div').classes('tf-hit') as hit:
            ui.html(f'<div class="tf-name">{html.escape(c["name"])}</div>'
                    f'<img class="tf-artimg" loading="lazy" src="/art/{c["num"]}_0.webp">'
                    f'<div class="tf-foot">{foot_text(c)}</div>', sanitize=False)
        if count:
            ui.html(f'<div class="tf-badge tf-count">×{count}</div>', sanitize=False)
        if picked:
            ui.html('<div class="tf-badge tf-check">✓</div>', sanitize=False)
        if c['allowed'] < 3:
            ui.html(f'<div class="tf-badge tf-limit">{["禁", "限1", "限2"][c["allowed"]]}</div>', sanitize=False)
        if c['arts'] > 1:
            ui.html(f'<div class="tf-badge tf-alt">异{c["arts"] - 1}</div>', sanitize=False)
        if on_plus or on_minus:
            # Siblings of .tf-hit, so pressing them does not also open the card.
            with ui.element('div').classes('tf-quick'):
                if on_minus:
                    ui.element('button').classes('tf-qbtn minus').on('click', on_minus).props('innerHTML="−"')
                if on_plus:
                    ui.element('button').classes('tf-qbtn plus').on('click', on_plus).props('innerHTML="+"')
    if on_click:
        hit.on('click', on_click)
    return tile


def real_card(c, art_index):
    glyph, color = ATTR.get(c['kind'], ('?', '#888'))
    stars = '★' * min(c['level'], 12) if c['kind'] not in ('Spell', 'Trap') else f"【{FRAME_LABEL[c['frame']]}】"
    typ = FRAME_LABEL[c['frame']] if c['kind'] not in ('Spell', 'Trap') else ''
    atk = f"ATK/{c['atk']}　DEF/{c['dfn']}" if c['kind'] not in ('Spell', 'Trap') else ''
    ui.html(f'''<div class="tf-real tf-{c['frame']}">
      <div class="tf-real-name"><span>{html.escape(c['name'])}</span>
        <span class="tf-adot2" style="background:{color}">{glyph}</span></div>
      <div class="tf-real-stars">{stars}</div>
      <img class="tf-real-art" src="/art/{c['num']}_{art_index}.webp">
      <div class="tf-real-text">{f'<div class="tf-real-type">【{typ}】</div>' if typ else ''}{html.escape(c['text'])}</div>
      <div class="tf-real-atk">{atk}</div></div>''', sanitize=False)


# ---------------------------------------------------------------- page

@ui.page('/')
def index():
    ui.add_css(CSS)
    dark = ui.dark_mode(True)
    st = dict(lang='zh', query='', kind='all', attr=None, owned_only=False, limit=120, tab='deck',
              slot=min(SLOTS) if SLOTS else 0, selected=None, history=[], art={},
              multi_cards=False, multi_deck=False, pick_cards=set(), pick_deck=set())

    def t(key):
        return TEXT[st['lang']][key]

    def load_slot(i):
        s = SLOTS.get(i) or dict(name=t('new_deck'), main=[], extra=[], side=[], ts=None)
        st.update(slot=i, name=s['name'], original={k: list(s[k]) for k in SECTIONS},
                  deck={k: list(s[k]) for k in SECTIONS}, history=[], pick_deck=set())
    load_slot(st['slot'])

    def counts():
        return collections.Counter(st['deck']['main'] + st['deck']['extra'] + st['deck']['side'])

    def problems():
        d, out = st['deck'], []
        if not 40 <= len(d['main']) <= 60:
            out.append(f"{t('main')} {len(d['main'])}/40–60")
        for sec in ('extra', 'side'):
            if len(d[sec]) > 15:
                out.append(f"{t(sec)} {len(d[sec])}/15")
        for n, k in collections.Counter(d['main'] + d['extra']).items():
            c = CARDS[n]
            cap = min(3, c['allowed'], c['owned'])
            if k > cap:
                out.append(f"{c['name']} ×{k} > {cap}")
        return out

    def snapshot():
        st['history'].append({k: list(v) for k, v in st['deck'].items()})

    def home(num):
        return 'extra' if CARDS[num]['frame'] in EXTRA_FRAMES else 'main'

    def change(sec, num, delta):
        snapshot()
        if delta > 0:
            st['deck'][sec].append(num)
        elif num in st['deck'][sec]:
            st['deck'][sec].remove(num)
        refresh_all()

    def undo():
        if st['history']:
            st['deck'] = st['history'].pop()
            refresh_all()

    # ---------- multi-select
    def toggle_multi(which):
        st[f'multi_{which}'] = not st[f'multi_{which}']
        st[f'pick_{which}'] = set()
        refresh_all()

    def add_picked(target):
        snapshot()
        for n in sorted(st['pick_cards']):
            st['deck'][home(n) if target == 'main' else 'side'].append(n)
        st['pick_cards'] = set()
        refresh_all()

    def move_picked(target):
        """Move every copy of each picked (section, card) to `target`; None removes them."""
        snapshot()
        for sec, n in sorted(st['pick_deck']):
            k = st['deck'][sec].count(n)
            st['deck'][sec] = [x for x in st['deck'][sec] if x != n]
            if target:
                st['deck'][target].extend([n] * k)
        st['pick_deck'] = set()
        refresh_all()

    async def tap_card(num):
        if st['multi_cards']:
            st['pick_cards'] ^= {num}
            browser_grid.refresh()
            return
        await select(num)

    async def tap_deck(sec, num):
        if st['multi_deck']:
            st['pick_deck'] ^= {(sec, num)}
            deck_view.refresh()
            return
        await select(num)

    async def select(num):
        st['selected'] = num
        detail.refresh()
        browser_grid.refresh()
        deck_view.refresh()
        if await ui.run_javascript('window.innerWidth') < 1024:
            sheet_body.refresh()
            sheet.open()

    def refresh_all():
        browser_grid.refresh()
        deck_view.refresh()
        detail.refresh()
        sheet_body.refresh()
        slot_list.refresh()

    def set_lang(v):
        st['lang'] = v
        rebuild()

    # ---------- header
    with ui.header().classes('items-center gap-2 px-3 py-2 bg-slate-900'):
        ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat round dense color=white')
        ui.label('TF Deck Studio').classes('text-lg font-bold text-white')
        ui.chip('游戏王 5D\'s TF6 · ULJM05940', icon='sports_esports').props('dense outline color=white') \
            .classes('tf-desktop-only')
        ui.space()
        ui.chip('Brick Pro · 192.168.0.12', icon='wifi').props('dense color=green-7 text-color=white') \
            .classes('tf-desktop-only')
        ui.toggle({'zh': '中', 'en': 'EN'}, value='zh', on_change=lambda e: set_lang(e.value)) \
            .props('dense rounded unelevated toggle-color=blue-6 color=grey-8 text-color=white')
        ui.button(icon='dark_mode', on_click=dark.toggle).props('flat round dense color=white')

    # ---------- slots drawer
    with ui.left_drawer(value=None).props('bordered width=260 breakpoint=1279').classes('p-2') as drawer:
        @ui.refreshable
        def slot_list():
            ui.label(t('slots')).classes('text-sm font-bold tf-muted px-2 pt-1')
            for i, s in sorted(SLOTS.items()):
                active = ' active' if i == st['slot'] else ''
                d = st['deck'] if i == st['slot'] else s
                with ui.element('div').classes('tf-slot' + active).on('click', lambda i=i: (load_slot(i), refresh_all())):
                    ui.label(st['name'] if i == st['slot'] else s['name']).classes('font-semibold')
                    ui.label(f"#{i}  ·  {len(d['main'])}/{len(d['extra'])}/{len(d['side'])}  ·  "
                             f"{s['ts'][0]}-{s['ts'][1]:02}-{s['ts'][2]:02}").classes('text-xs tf-muted')
            free = next(i for i in range(NSLOTS) if i not in SLOTS)
            ui.button(t('new_deck'), icon='add', on_click=lambda: (load_slot(free), refresh_all())) \
                .props('flat color=primary').classes('w-full mt-1')
            ui.separator().classes('my-2')
            ui.label(t('partner')).classes('text-sm font-bold tf-muted px-2')
            ui.label('123 · 0x154C0').classes('text-xs tf-muted px-2')
        slot_list()

    # ---------- mobile footer tabs
    def set_tab(key):
        st['tab'] = key
        panels.refresh()
        footer_tabs.refresh()

    with ui.footer().classes('tf-mobile-only bg-slate-900 p-0'):
        @ui.refreshable
        def footer_tabs():
            with ui.row().classes('w-full no-wrap gap-0'):
                for key, icon in (('deck', 'style'), ('cards', 'grid_view')):
                    active = st['tab'] == key
                    ui.button(t(key), icon=icon, on_click=lambda k=key: set_tab(k)) \
                        .props(f"flat stack no-caps square color={'amber-5' if active else 'grey-5'}") \
                        .classes('flex-1 tf-tab' + (' tf-tab-on' if active else ''))
        footer_tabs()

    # ---------- detail (desktop panel and phone sheet)
    def detail_content():
        num = st['selected']
        if num is None:
            ui.label(t('empty')).classes('tf-muted m-auto p-6')
            return
        c = CARDS[num]
        k = st['art'].get(num, 0)
        real_card(c, k)
        if c['arts'] > 1:
            with ui.row().classes('w-full items-center justify-center gap-2 mt-1'):
                ui.button(icon='chevron_left', on_click=lambda: (st['art'].update({num: (k - 1) % c['arts']}),
                                                                 detail.refresh(), sheet_body.refresh())) \
                    .props('flat round')
                ui.label(f"{t('alt')} {k + 1}/{c['arts']}").classes('text-sm')
                ui.button(icon='chevron_right', on_click=lambda: (st['art'].update({num: (k + 1) % c['arts']}),
                                                                  detail.refresh(), sheet_body.refresh())) \
                    .props('flat round')
        in_deck = {s: st['deck'][s].count(num) for s in SECTIONS}
        with ui.element('div').classes('grid grid-cols-2 gap-2 w-full mt-3'):
            sec = home(num)
            ui.button(t('add_extra') if sec == 'extra' else t('add_main'), icon='add',
                      on_click=lambda: change(sec, num, 1)) \
                .props('unelevated color=primary no-caps').classes('tf-big-btn')
            ui.button(t('add_side'), icon='add', on_click=lambda: change('side', num, 1)) \
                .props('outline color=primary no-caps').classes('tf-big-btn')
            rm = next((s for s in ('side', 'extra', 'main') if in_deck[s]), None)
            ui.button(t('remove'), icon='remove', on_click=lambda: change(rm, num, -1)) \
                .props('outline color=negative no-caps').classes('tf-big-btn col-span-2').set_enabled(rm is not None)
        in_text = ' · '.join(f"{t(s)} ×{n}" for s, n in in_deck.items() if n)
        rows = [(t('number'), c['num']), (t('passcode'), c['pas'] or '—'), (t('owned'), c['owned']),
                (t('limit'), ['禁止', '限制 1', '准限制 2', '无限制'][c['allowed']])]
        with ui.element('div').classes('grid grid-cols-4 gap-x-2 text-xs mt-3 w-full'):
            for key, v in rows:
                ui.label(key).classes('tf-muted')
                ui.label(str(v))
        if in_text:
            ui.label(in_text).classes('text-xs mt-1')
        used = [s['name'] for i, s in SLOTS.items() if num in s['main'] + s['extra'] + s['side']]
        if used:
            ui.label(f"{t('used_in')}: {'、'.join(used)}").classes('text-xs tf-muted')

    with ui.dialog().props('position=bottom') as sheet, \
            ui.card().classes('w-full p-3').style('max-height:88dvh; overflow:auto'):
        @ui.refreshable
        def sheet_body():
            with ui.element('div').classes('w-full').style('max-width:340px; margin:0 auto'):
                detail_content()
        sheet_body()

    # ---------- card browser
    def filtered():
        q = search_key(st['query'])
        out = []
        for c in ORDER:
            if st['kind'] == 'monster' and c['kind'] in ('Spell', 'Trap'):
                continue
            if st['kind'] in ('Spell', 'Trap') and c['kind'] != st['kind']:
                continue
            if st['attr'] and c['kind'] != st['attr']:
                continue
            if st['owned_only'] and not c['owned']:
                continue
            if q and q not in c['key'] and q != str(c['num']) and q != str(c['pas']):
                continue
            out.append(c)
        return out

    def pickbar(text, actions, clear):
        with ui.row().classes('tf-pickbar items-center gap-1 no-wrap'):
            ui.label(text).classes('font-bold text-sm whitespace-nowrap')
            ui.space()
            for label, icon, fn in actions:
                ui.button(label, icon=icon, on_click=fn).props('unelevated dense no-caps color=grey-10 size=md')
            ui.button(icon='close', on_click=clear).props('flat round dense color=grey-10').tooltip(t('clear'))

    @ui.refreshable
    def browser_grid():
        res, cnt = filtered(), counts()
        with ui.row().classes('items-center w-full mb-1'):
            ui.label(f"{len(res)} {t('results')}").classes('text-xs tf-muted')
        if st['multi_cards'] and st['pick_cards']:
            pickbar(f"{t('picked')} {len(st['pick_cards'])}",
                    [(t('add_main'), 'add', lambda: add_picked('main')),
                     (t('add_side'), 'add', lambda: add_picked('side'))],
                    lambda: (st.update(pick_cards=set()), browser_grid.refresh()))
        with ui.element('div').classes('tf-grid'):
            for c in res[:st['limit']]:
                n = c['num']
                card_tile(c, count=cnt.get(n, 0), selected=n == st['selected'], picked=n in st['pick_cards'],
                          on_click=lambda n=n: tap_card(n),
                          on_plus=None if st['multi_cards'] else (lambda n=n: change(home(n), n, 1)))
        if len(res) > st['limit']:
            ui.button(t('more'), on_click=lambda: (st.update(limit=st['limit'] + 120), browser_grid.refresh())) \
                .props('flat color=primary').classes('w-full mt-2')

    # ---------- deck
    @ui.refreshable
    def deck_view():
        d = st['deck']
        issues = problems()
        with ui.row().classes('items-center gap-2 px-3 pt-3 w-full no-wrap'):
            ui.input(value=st['name'], on_change=lambda e: st.update(name=e.value)) \
                .props('dense borderless input-class="text-lg font-bold"').classes('flex-1 min-w-0')
            ui.button(t('multi'), icon='checklist', on_click=lambda: toggle_multi('deck')) \
                .props(f"{'unelevated color=amber-7 text-color=black' if st['multi_deck'] else 'outline'} dense no-caps")
            ui.label(f"#{st['slot']}").classes('tf-muted text-xs')
        with ui.row().classes('gap-1 px-3 pb-2'):
            for sec, lo, hi in (('main', 40, 60), ('extra', 0, 15), ('side', 0, 15)):
                ok = lo <= len(d[sec]) <= hi
                ui.chip(f"{t(sec)} {len(d[sec])}", icon='check' if ok else 'error') \
                    .props(f"dense {'color=green-1 text-color=green-9' if ok else 'color=red-1 text-color=red-9'}")
            if not issues:
                ui.chip(t('ok'), icon='verified').props('dense color=blue-1 text-color=blue-9')
        for msg in issues[:4]:
            ui.label('⚠ ' + msg).classes('text-xs text-red-500 px-3')
        if st['multi_deck'] and st['pick_deck']:
            secs = {s for s, _ in st['pick_deck']}
            moves = [(t(f'to_{s}'), 'drive_file_move', lambda s=s: move_picked(s)) for s in SECTIONS if {s} != secs]
            pickbar(f"{t('picked')} {len(st['pick_deck'])} {t('kinds')}",
                    moves + [(t('delete'), 'delete', lambda: move_picked(None))],
                    lambda: (st.update(pick_deck=set()), deck_view.refresh()))
        with ui.element('div').classes('tf-scroll'):
            for sec in SECTIONS:
                cnt = collections.Counter(d[sec])
                with ui.element('div').classes('tf-section-title'):
                    ui.label(t(sec))
                    ui.label(str(len(d[sec]))).classes('tf-muted')
                if not cnt:
                    ui.label('—').classes('tf-muted text-xs px-1 mb-2')
                    continue
                order = sorted(cnt, key=lambda n: ({'spell': 1, 'trap': 2}.get(CARDS[n]['frame'], 0),
                                                   -CARDS[n]['level'], n))
                with ui.element('div').classes('tf-grid mb-3'):
                    for n in order:
                        quick = not st['multi_deck']
                        card_tile(CARDS[n], count=cnt[n], selected=n == st['selected'],
                                  picked=(sec, n) in st['pick_deck'],
                                  on_click=lambda s=sec, n=n: tap_deck(s, n),
                                  on_plus=(lambda s=sec, n=n: change(s, n, 1)) if quick else None,
                                  on_minus=(lambda s=sec, n=n: change(s, n, -1)) if quick else None)
        with ui.row().classes('tf-actions no-wrap items-center gap-1 p-2 border-t w-full').style('border-color:var(--tf-line)'):
            for label, icon, handler in ((t('undo'), 'undo', undo), (t('import_'), 'content_paste', None),
                                         (t('export'), 'download', None)):
                b = ui.button(icon=icon, on_click=handler).props('flat round').tooltip(label)
                if handler is undo:
                    b.set_enabled(bool(st['history']))
            ui.space()
            ui.button(t('push'), icon='upload', on_click=show_diff).props('unelevated color=primary no-caps')

    def show_diff():
        with ui.dialog() as dlg, ui.card().classes('min-w-[300px]'):
            ui.label(t('diff_title')).classes('text-lg font-bold')
            ui.label(f"#{st['slot']} {st['name']}").classes('tf-muted')
            changed = False
            for sec in SECTIONS:
                a, b = collections.Counter(st['original'][sec]), collections.Counter(st['deck'][sec])
                for n in sorted(set(a) | set(b)):
                    if a[n] != b[n]:
                        changed = True
                        color = 'text-green-600' if b[n] > a[n] else 'text-red-500'
                        ui.label(f"{t(sec)} · {CARDS[n]['name']}: {a[n]} → {b[n]}").classes(f'text-sm {color}')
            if not changed:
                ui.label(t('no_change')).classes('tf-muted')
            ui.label('backup → encrypt → verify → push → md5').classes('text-xs tf-muted mt-2')
            with ui.row().classes('w-full justify-end'):
                ui.button(t('cancel'), on_click=dlg.close).props('flat')
                ui.button(t('confirm')).props('unelevated color=primary').set_enabled(False)
        dlg.open()

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
                        ui.input(placeholder=t('search'), value=st['query'],
                                 on_change=lambda e: (st.update(query=e.value or '', limit=120), browser_grid.refresh())) \
                            .props('outlined dense clearable rounded debounce=150').classes('flex-1') \
                            .add_slot('prepend', '<q-icon name="search" />')
                        ui.button(t('multi'), icon='checklist', on_click=lambda: (toggle_multi('cards'), panels.refresh())) \
                            .props(f"{'unelevated color=amber-7 text-color=black' if st['multi_cards'] else 'outline'} no-caps")
                    with ui.row().classes('items-center gap-2 w-full'):
                        ui.toggle({'all': t('all'), 'monster': t('monster'), 'Spell': t('spell'), 'Trap': t('trap')},
                                  value=st['kind'],
                                  on_change=lambda e: (st.update(kind=e.value, limit=120), browser_grid.refresh())) \
                            .props('dense no-caps rounded unelevated toggle-color=primary')
                        ui.select({None: t('attr'), **{k: v[0] for k, v in ATTR.items() if k not in ('Spell', 'Trap')}},
                                  value=st['attr'],
                                  on_change=lambda e: (st.update(attr=e.value, limit=120), browser_grid.refresh())) \
                            .props('dense outlined options-dense').classes('w-24')
                        ui.switch(t('owned_only'), value=st['owned_only'],
                                  on_change=lambda e: (st.update(owned_only=e.value), browser_grid.refresh())).props('dense')
                with ui.element('div').classes('tf-scroll'):
                    browser_grid()
            with ui.element('div').classes('tf-panel' + ('' if st['tab'] == 'deck' else ' tf-inactive')):
                deck_view()
            with ui.element('div').classes('tf-panel tf-detail-panel'):
                detail()

    def rebuild():
        panels.refresh()
        footer_tabs.refresh()
        slot_list.refresh()
        sheet_body.refresh()

    panels()
    ui.label(t('mock')).classes('fixed bottom-1 right-3 text-[10px] tf-muted tf-desktop-only')


ui.run(title='TF Deck Studio (mock)', host='0.0.0.0', port=8080, reload=False, show=False, dark=True)
