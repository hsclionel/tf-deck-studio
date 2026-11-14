"""Per-game constants. Japan-only releases; fan patches keep these disc IDs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Game:
    disc_id: str
    short: str
    title: str
    plain_size: int          # decrypted DATA0 size
    decks_supported: bool    # deck layout verified in-game
    first_card: int = 3459   # card number range of the game's database
    last_card: int = 9839
    trunk: int = 0x29418     # card collection: 4 bytes per database row


# Both games log this key when they save (PPSSPP "Game key (hex)"); verified 2026-10-27.
TAG_FORCE_KEY = bytes.fromhex('29AF6F5E02F970D52E2412C7E1FC83BA')

GAMES = {
    'ULJM05940': Game('ULJM05940', 'TF6', "Yu-Gi-Oh! 5D's Tag Force 6", 0x47000, True),
    'NPJH50794': Game('NPJH50794', 'TF6', "Yu-Gi-Oh! 5D's Tag Force 6 (PSN)", 0x47000, True),
    # TFSP: same deck slots as TF6 (mapped 2026-10-28 by renaming a deck in-game and diffing);
    # trunk found by the token rows, which are the only cards with owned 0.
    'NPJH00142': Game('NPJH00142', 'TFSP', 'Yu-Gi-Oh! ARC-V Tag Force Special', 0x48000, True,
                      last_card=11657, trunk=0x33A24),
}

CARDINFO_PATH = 'PSP_GAME/USRDIR/duelsys/cardinfo_jpn.ehp'
CARD_ART_PATH = 'PSP_GAME/USRDIR/card/cardh_j.cip'


def game_for_save_dir(name):
    """'ULJM059400001' → Game, or None."""
    return GAMES.get(name[:9].upper())
