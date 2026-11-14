"""Built-in data for game-original cards, one file per game (tfcore/gamecards/<game>.json).

These are the cards no outside database can describe: game/anime-original cards without a
real-world passcode, plus game-specific versions ygocdb does not list. Without them a save opened
without its ISO would show those cards as bare numbers. Name, type, stats and effect text come
from the game data of the ISO the file was generated from (here the Chinese patches).

The files hold text from the game, so they are not part of the public repository (.gitignore):
generate them from your own ISO with `python -m tfcore.cli pool <iso> [--names cards.json]`.
Without them, game-original cards show as bare numbers when a save is opened without its ISO.
"""
import json, os
from dataclasses import asdict

from .carddb import Card

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gamecards')
FIELDS = ('num', 'passcode', 'name', 'text', 'attribute', 'frame', 'level', 'atk', 'defense', 'tuner', 'race')


def select(db, names_db=None):
    """Card numbers that need built-in data: passcode 0, or unknown to ygocdb."""
    return sorted(n for n, c in db.cards.items() if not c.passcode or (names_db is not None and n not in names_db))


def export(game_short, db, nums, source_label, path=None):
    path = path or os.path.join(DIR, f'{game_short}.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = [{k: v for k, v in asdict(db.cards[n]).items() if k in FIELDS} for n in nums]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'game': game_short, 'source': source_label, 'count': len(rows), 'cards': rows}, f,
                  ensure_ascii=False, separators=(',', ':'))
    return path


def load(game_short):
    """num → Card, or {} when the game has no file."""
    path = os.path.join(DIR, f'{game_short}.json')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {r['num']: Card(row=0, arts=0, game_only=not r['passcode'], **{'tuner': 0, 'race': '', **r}) for r in data['cards']}
