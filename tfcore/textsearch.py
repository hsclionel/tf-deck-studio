"""How the card browser matches what the user typed (issue #2: effect text is searchable too).

A query is matched against three things: the card name (including alternate names), the card
number/passcode, and the effect text. Names and numbers outrank effect text — searching "抽卡"
should list 强欲之壶 (its name has no 抽卡, its text does) *below* every card whose name matched,
not mixed in with them.

Lives in tfcore (not app/) so the tests can cover it without importing NiceGUI.
"""
import re
import unicodedata

#: Full-width→half-width happens first, then these go: separating punctuation carries no meaning
#: in a name or an effect line, and the game's own text uses them liberally.
SEPARATORS = re.compile(r'[\s·・\-－_.,，。!！、；;：:（）()「」『』]')

NAME_HIT, TEXT_HIT, NO_HIT = 2, 1, 0


def normalize(s):
    """Normalize a name or an effect line for matching: 'Ｅ·ＨＥＲＯ　天空侠' → 'ehero天空侠'."""
    return SEPARATORS.sub('', unicodedata.normalize('NFKC', s)).lower()


def hit(query, name_key, text_key, numbers=()):
    """Where a normalized `query` matched: the name (or a number), the effect text, or nowhere.

    `numbers` holds the card number and the passcode (None when the card has none); they count as
    NAME_HIT, so a number search is not pushed below cards that merely mention it in their text.
    """
    if not query:
        return NO_HIT
    if query in name_key or any(query in str(n) for n in numbers if n):
        return NAME_HIT
    return TEXT_HIT if query in text_key else NO_HIT


def rank(query, name_key, text_key, numbers=()):
    """Sort key for a search result list: higher first, so names stay above effect-text matches."""
    return -hit(query, name_key, text_key, numbers)
