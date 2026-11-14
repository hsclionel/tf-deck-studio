"""Role tags for the card browser (手坑, 墓地效果, trap roles, staples …).

Rule-based from the card's Chinese effect text, which comes from the user's ISO (or the built-in
game-card file / ygocdb text). TF6 and TFSP word the same effect differently ("手卡/手牌",
"从游戏中除外/除外", "·/・"), so the patterns accept both. Staples (通用强卡) are a short
built-in list of card numbers (`tags_staples.json`, IDs only) plus the user's own marks.
"""
import json, os, re

# key → label, in the order the filter menu shows them
TAGS = {
    'staple': '通用强卡',
    'tuner': '调整',
    'handtrap': '手坑',
    'gy': '墓地发动',
    'sent': '送墓触发',
    'negate': '无效',
    'summon_react': '召唤反应坑',
    'attack_react': '攻击反应坑',
    'wipe': '全场破坏',
    'search': '检索',
    'draw': '抽卡',
    'revive': '苏生',
    'limited': '禁限卡',
}

# Hand traps: the card pays its own cost from the hand (discard / send / banish) at a time the
# opponent controls, or special summons itself from the hand during a battle (Gorz, Battle Fader).
_SELF_COST = re.compile(r'这张卡从手[卡牌](?:丢弃|送去墓地|送入墓地|除外)|手[卡牌]的这张卡(?:丢弃|送去墓地|除外)|'
                        r'从手[卡牌](?:把|将)?这张卡(?:丢弃|送去墓地|除外)')
_SELF_SS = re.compile(r'这张卡(?:可以)?从手[卡牌](?:表侧[^。，]{0,6})?特殊召唤|从手[卡牌](?:把|将)?这张卡特殊召唤')
_OPP_TIME = re.compile(r'对方(?:的)?回合|对方(?:的)?(?:主要|战斗|准备|抽卡|结束)阶段|攻击宣言|伤害(?:步骤|计算)|'
                       r'受到(?:战斗)?伤害|对方[^。]{0,20}(?:发动|召唤)(?:时|之际)|对方回合也能发动')
_BATTLE_TIME = re.compile(r'攻击宣言|伤害(?:步骤|计算)|受到(?:战斗)?伤害|战斗伤害')
_GY = re.compile(r'墓地(?:存在)?的这张卡|这张卡在墓地|这张卡(?:存在)?于墓地|这张卡从墓地')
_SENT = re.compile(r'这张卡[^。，；]{0,12}?(?:送去|送进|送入)墓地(?:的场合|时|的时候)')
_SUMMON_REACT = re.compile(r'召唤[·・]反转召唤[·・]特殊召唤(?:的)?(?:时候|时|之际)|召唤(?:成功)?(?:的)?(?:时候|时|之际)才(?:能|可以)发动|特殊召唤(?:成功)?时才能发动')
_ATTACK_REACT = re.compile(r'攻击宣言时|攻击宣言的时候')
_WIPE = re.compile(r'(?:场上|对方场上)(?:的)?(?:怪兽|魔法[·・]陷阱卡|卡)全部(?:破坏|除外|回到)|全部(?:怪兽|卡)?破坏|全破坏')
# TF6 wording puts the noun after 全部: 「对方场上存在的全部怪兽破坏」 (雷击, 黑洞, 封魔一闪)
_SEARCH = re.compile(r'卡组[^。]{0,40}?加入(?:到)?(?:自己的?)?手[卡牌]')
_DRAW = re.compile(r'(?:从卡组)?抽[１２３1-3]张')
_REVIVE = re.compile(r'墓地.{0,24}怪兽.{0,16}特殊召唤|从墓地特殊召唤')
_NEGATE = re.compile(r'(?:发动|召唤|效果)(?:无效|变成无效)|无效并破坏|效果直到[^。]{0,10}无效')

_STAPLES = os.path.join(os.path.dirname(__file__), 'tags_staples.json')
_staples = None


def staples():
    """Built-in staple card numbers (both games share Konami IDs)."""
    global _staples
    if _staples is None:
        with open(_STAPLES, encoding='utf-8') as f:
            _staples = set(json.load(f)['cards'])
    return _staples


def _sentences(text):
    return [s for s in re.split(r'[。\n]', text) if s]


def from_text(card):
    """Tags that follow from the card's own text and type (no staple / ban list)."""
    t, out = card.text or '', set()
    monster = card.is_monster
    if monster and card.tuner:                       # card type, not text: Tuner or the game's Dark Tuners
        out.add('tuner')
    if monster and not card.extra_deck and (
            _SELF_COST.search(t) and _OPP_TIME.search(t) or _SELF_SS.search(t) and _BATTLE_TIME.search(t)):
        out.add('handtrap')
    if _GY.search(t):
        out.add('gy')
    if _SENT.search(t):
        out.add('sent')
    if card.attribute == 'TRAP':
        if _SUMMON_REACT.search(t):
            out.add('summon_react')
        if _ATTACK_REACT.search(t):
            out.add('attack_react')
    if _NEGATE.search(t) and (card.attribute == 'TRAP' or 'handtrap' in out or monster):
        out.add('negate')
    if _WIPE.search(t):
        out.add('wipe')
    if _SEARCH.search(t):
        out.add('search')
    if _DRAW.search(t):
        out.add('draw')
    if not monster and _REVIVE.search(t):
        out.add('revive')
    return out


def tags_of(card, allowed=3, extra_staples=(), not_staples=()):
    """All tags for one card; `allowed` is the save's ban-list limit (3 = unlimited)."""
    out = from_text(card)
    if (card.num in staples() or card.num in extra_staples) and card.num not in not_staples:
        out.add('staple')
    if allowed < 3:
        out.add('limited')
    return out
