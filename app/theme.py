"""Labels and card widgets shared by the app pages."""
import html, re, unicodedata

from nicegui import ui

from theme_css import CSS, EXTRA_CSS

__all__ = ['CSS', 'EXTRA_CSS', 'ATTR', 'FRAME_LABEL', 'View', 'card_tile', 'real_card', 'search_key']

ATTR = {'LIGHT': ('光', '#e8b923'), 'DARK': ('暗', '#7b5ea7'), 'WATER': ('水', '#3d8fd6'),
        'FIRE': ('炎', '#e4572e'), 'EARTH': ('地', '#8d6236'), 'WIND': ('风', '#3fa363'),
        'DIVINE': ('神', '#c99a1c'), 'SPELL': ('魔', '#1f9e89'), 'TRAP': ('罠', '#b44f8a'), '?': ('?', '#6b7280')}
FRAME_LABEL = {'normal': '通常', 'effect': '效果', 'fusion': '融合', 'synchro': '同调', 'darksynchro': '黑暗同调', 'xyz': '超量',
               'ritual': '仪式', 'pendulum': '灵摆', 'token': '衍生物', 'link': '连接', 'spell': '魔法卡', 'trap': '陷阱卡'}
LIMIT_LABEL = ['禁', '限1', '限2']
TUNER_LABEL = {1: '调整', 2: '黑暗调整'}


def search_key(s):
    """Full-width → half-width, lower case, separators dropped: 'Ｅ·ＨＥＲＯ　天空侠' → 'ehero天空侠'."""
    return re.sub(r'[\s·・\-－_.,，。!！]', '', unicodedata.normalize('NFKC', s)).lower()


def stat(x):
    """ATK/DEF for display: -1 is the card's "?"."""
    return '?' if x < 0 else x


class View:
    """What the widgets need to know about one card in the current session."""
    __slots__ = ('card', 'art', 'owned', 'allowed', 'addable', 'key', 'tags')

    def __init__(self, card, art, trunk, addable, alt_names):
        self.card = card
        self.art = art                                  # callable k -> URL, or None
        self.owned, self.allowed = trunk if trunk else (None, 3)
        self.addable = addable
        self.key = search_key(' '.join([card.name, *alt_names.values()]))
        self.tags = frozenset()                         # tfcore.tags keys, set by the editor

    @property
    def is_spelltrap(self):
        return self.card.attribute in ('SPELL', 'TRAP')

    def foot(self):
        c = self.card
        if self.is_spelltrap:
            return FRAME_LABEL[c.frame]
        if c.attribute == '?':
            return f'#{c.num}'
        return f"{'★' * min(c.level, 12)} {stat(c.atk)}/{stat(c.defense)}"


def _art_html(v, k, cls):
    if v.art:
        return f'<img class="{cls}" loading="lazy" src="{v.art(k)}">'
    glyph, color = ATTR.get(v.card.attribute, ATTR['?'])
    return (f'<div class="tf-noart" style="background:radial-gradient(circle at 50% 40%, {color}, '
            f'rgba(0,0,0,.35))">{glyph}</div>')


def card_tile(v, count=0, selected=False, picked=False, on_click=None, on_plus=None, on_minus=None, fav=False):
    c = v.card
    classes = (f'tf-card tf-{c.frame}' + (' sel' if selected else '') + (' picked' if picked else '')
               + ('' if v.addable else ' locked'))
    with ui.element('div').classes(classes) as tile:
        with ui.element('div').classes('tf-hit') as hit:
            ui.html(f'<div class="tf-name">{html.escape(c.name)}</div>{_art_html(v, 0, "tf-artimg")}'
                    f'<div class="tf-foot">{v.foot()}</div>', sanitize=False)
        if count:
            ui.html(f'<div class="tf-badge tf-count">×{count}</div>', sanitize=False)
        if picked:
            ui.html('<div class="tf-badge tf-check">✓</div>', sanitize=False)
        if v.allowed < 3:
            ui.html(f'<div class="tf-badge tf-limit">{LIMIT_LABEL[v.allowed]}</div>', sanitize=False)
        if c.arts > 1:
            ui.html(f'<div class="tf-badge tf-alt">异{c.arts - 1}</div>', sanitize=False)
        if c.game_only:
            ui.html('<div class="tf-badge tf-orig">原创</div>', sanitize=False)
        if c.tuner and c.is_monster:
            ui.html(f'<div class="tf-badge tf-tuner{c.tuner}">{TUNER_LABEL[c.tuner]}</div>', sanitize=False)
        if fav:
            ui.html('<div class="tf-badge tf-fav">♥</div>', sanitize=False)
        if not v.addable:
            ui.html('<div class="tf-badge tf-lock">🔒</div>', sanitize=False)
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


def real_card(v, art_index):
    c = v.card
    glyph, color = ATTR.get(c.attribute, ATTR['?'])
    stars = f'【{FRAME_LABEL[c.frame]}】' if v.is_spelltrap else '★' * min(c.level, 12)
    race = f'{c.race}族' if c.race else ''
    typ = '' if v.is_spelltrap else '／'.join(x for x in (race, FRAME_LABEL.get(c.frame, ''), TUNER_LABEL.get(c.tuner)) if x)
    atk = '' if v.is_spelltrap or c.attribute == '?' else f'ATK/{stat(c.atk)}　DEF/{stat(c.defense)}'
    text = html.escape(c.text) if c.text else '<span style="opacity:.6">（没有效果文字：请添加游戏 ISO 或下载卡名库）</span>'
    ui.html(f'''<div class="tf-real tf-{c.frame}">
      <div class="tf-real-name"><span>{html.escape(c.name)}</span>
        <span class="tf-adot2" style="background:{color}">{glyph}</span></div>
      <div class="tf-real-stars">{stars}</div>
      {_art_html(v, art_index, "tf-real-art")}
      <div class="tf-real-text">{f'<div class="tf-real-type">【{typ}】</div>' if typ else ''}{text}</div>
      <div class="tf-real-atk">{atk}</div></div>''', sanitize=False)
