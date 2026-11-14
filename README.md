# TF Deck Studio

A deck editor for the PSP games **Yu-Gi-Oh! 5D's Tag Force 6** (ULJM05940) and
**Yu-Gi-Oh! ARC-V Tag Force Special** (NPJH00142). It opens the game's encrypted save, lets you
build and edit decks in a browser UI, and writes the save back so the game loads it.

- Card browser with art and effect text from your own ISO, search in Chinese/Japanese/English,
  filters by attribute, level, frame (Fusion/Synchro/Xyz), role tags and favourites.
- Deck checks against the save's ban list and your owned cards; similar-card suggestions for
  cards over the limit or missing from the game.
- Import from YDK files, ydke:// links and pasted deck lists; a library of your own decks and the
  games' own recipes.
- Unsaved edits survive a page reload; backups before every write.
- Optional sync with a handheld over SSH (TrimUI devices on NextUI/NX Redux or spruceOS).

It ships **no game data**. You need your own copy of the game (ISO) for card data and art.

## Run

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app\main.py --port 8080
```

Then open http://localhost:8080, add your ISO and open a save folder
(`PSP/SAVEDATA/ULJM059400001` or `NPJH001420001`).

Tests: `.venv\Scripts\python -m pytest`. Most tests need your own ISOs and saves and are
skipped without them (see `tests/conftest.py`).

## Safety

Always keep a copy of your save. The app backs up the save before each write, but it is an
unofficial tool. Don't load an emulator save state taken before an edit: it puts the old decks
back in memory.

## Licence

GPL-3.0-or-later, see `LICENSE`. Credits, third-party licences and data sources are in
`CREDITS.md`. Yu-Gi-Oh! is a trademark of Konami; this is an unofficial, non-commercial fan tool.
