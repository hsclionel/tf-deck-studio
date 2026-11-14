"""Fixtures come from the user's own saves (backups/, testdata/) and ISOs (C:\\game by default;
override with TF6_ISO / TFSP_ISO). ISO-based tests are skipped when the ISO is missing."""
import os, pathlib, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tfcore import iso  # noqa: E402
from tfcore.games import CARDINFO_PATH  # noqa: E402

BACKUPS = ROOT / 'backups'
MEMSTICK = ROOT / 'testdata' / 'memstick' / 'PSP' / 'SAVEDATA'
TF6_ISO = os.environ.get('TF6_ISO', r'C:\game\TagForce6_CHS_D0.86.iso')
TFSP_ISO = os.environ.get('TFSP_ISO', r'C:\game\游戏王 卡片力量SP [v1.00][PLAY汉化组].iso')

# The TF6 edit chain; every step was loaded in-game on 2026-10-27.
CHAIN = [BACKUPS / 'ULJM059400001_20261027_orig', BACKUPS / 'ULJM059400001_20261027_renamed',
         BACKUPS / 'ULJM059400001_20261027_ehero', MEMSTICK / 'ULJM059400001']
ALL_SAVES = CHAIN + [MEMSTICK / 'NPJH001420001']


def _cardinfo(path):
    if not os.path.exists(path):
        pytest.skip(f'ISO not found: {path}')
    return iso.fetch(iso.open_iso(path), CARDINFO_PATH)


@pytest.fixture(scope='session')
def tf6_db():
    from tfcore.carddb import CardDB
    return CardDB(_cardinfo(TF6_ISO))


@pytest.fixture(scope='session')
def tfsp_db():
    from tfcore.carddb import CardDB
    return CardDB(_cardinfo(TFSP_ISO))
