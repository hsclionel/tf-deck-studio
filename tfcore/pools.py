"""Built-in card-number lists ("pools"), one per game: the only game-derived data the app ships.

A pool is just the sorted card numbers the game's database contains (stored as runs). It holds no
names, texts or images. It is what lets a save be read without the ISO: the trunk stores one
record per database row, and row N is the N-th card number of the pool (row 0 is a dummy) —
verified for every card of TF6 and TFSP on 2026-10-27.

Regenerate from an ISO with `python -m tfcore.cli pool <iso>`; an added ISO is checked against it.
"""
import bisect, json, os

POOL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pools')


def _runs(nums):
    runs = []
    for n in sorted(nums):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return runs


class Pool:
    def __init__(self, game, nums):
        self.game = game
        self.nums = sorted(nums)
        self._set = set(self.nums)

    def __contains__(self, num):
        return num in self._set

    def __len__(self):
        return len(self.nums)

    def row_of(self, num):
        """Trunk row of a card number, 0 if the game lacks the card."""
        if num not in self._set:
            return 0
        return bisect.bisect_left(self.nums, num) + 1

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'game': self.game, 'count': len(self.nums), 'runs': _runs(self.nums)}, f, separators=(',', ':'))


def load(game_short):
    path = os.path.join(POOL_DIR, f'{game_short}.json')
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    nums = [n for a, b in data['runs'] for n in range(a, b + 1)]
    if len(nums) != data['count']:
        raise ValueError(f'{path}: pool count mismatch')
    return Pool(data['game'], nums)


def from_carddb(game_short, db):
    return Pool(game_short, db.cards)


def matches(pool, db):
    """True when an ISO's card database agrees with the built-in pool (same cards, same rows)."""
    return pool is not None and pool.nums == sorted(db.cards) and all(pool.row_of(n) == db.row_of(n) for n in pool.nums)
