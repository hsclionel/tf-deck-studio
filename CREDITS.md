# Credits and licences

TF Deck Studio is licensed under the **GNU General Public License v3.0 or later** (see `LICENSE`).
It has to be GPL: its save encryption is ported from PPSSPP (GPL-2.0-or-later), and every PSP
save-crypto implementation found descends from GPL code. GPL-3.0-or-later is used because it can
include that GPL-2.0-or-later code and also the Apache-2.0 licensed libraries the app depends on.

## Code ported or adapted

| Where | From | Licence | What was used |
|---|---|---|---|
| `tfcore/savecrypto.py`, `legacy/tfcrypt.py` | [PPSSPP](https://github.com/hrydgard/ppsspp) `Core/HLE/sceChnnlsv.cpp`, `Core/Dialog/SavedataParam.cpp`, `ext/libkirk` | GPL-2.0-or-later | PSP savedata encryption (sceChnnlsv modes 1/3/5), PARAM.SFO hashing, KIRK keys |
| `legacy/kirk_engine.c` | libkirk / KIRK engine by Draan, with coyotebean, Davee, hitchhikr, kgsws, liquidzigong, Mathieulh, Proxima, SilverSpring (as distributed with PPSSPP) | GPL-3.0-or-later | Reference copy of the KIRK engine (not used by the app) |
| `tfcore/carddb.py` (`huffman_text`), `legacy/carddb.py` | [ogy](https://github.com/exsilium/ogy) by Sten Feldman | BSD-2-Clause (licence text below) | Tag Force card-text Huffman decoding algorithm |

## Formats and research this project relied on (no code copied)

- [eireetm/ygotfToolkit](https://github.com/eireetm/ygotfToolkit): Tag Force save and file format documentation.
- [xan1242/tfcardedit](https://github.com/xan1242/tfcardedit) (MIT) and [xan1242/tfcardeditgui](https://github.com/xan1242/tfcardeditgui): Tag Force CardInfo layout.
- [PPSSPP](https://www.ppsspp.org/): emulator used to test saves.

## Online data used at runtime (nothing bundled)

The app downloads these only when the user asks, into the user's own cache. None of their data is in this repository except card numbers and passcodes (facts, no text).

| Service | Used for | Terms |
|---|---|---|
| [ygocdb.com](https://ygocdb.com) | Official Chinese/Japanese/English card names, card table when no ISO is added | No licence stated; downloaded per user, never redistributed |
| [YGOPRODeck card API](https://ygoprodeck.com/api-guide/) | Alternate passcodes → card numbers (`tfcore/passcodes_alt.json` holds numbers only) | API guide terms. Deck data is not downloaded; the owner declined deck APIs ([AlanOC91/YGOPRODeck#530](https://github.com/AlanOC91/YGOPRODeck/issues/530)). Users open the site and export decks themselves |
| [Yugipedia](https://yugipedia.com) | Character deck recipes for Tag Force 6 | Text under CC BY-SA 4.0; downloaded per user via its API |

## Game data

No game data is distributed. Card tables, effect text, artwork and the games' own deck recipes are
read from the user's own ISO at runtime, and decks from the user's own save. The files under
`tfcore/pools/`, `tags_staples.json`, `standins.json`, `nicknames.json` and `passcodes_alt.json`
contain card numbers, passcodes and community nicknames only.

`tfcore/gamecards/*.json` (game-original cards for use without an ISO) contains text from the game
and is therefore not published; generate it from your ISO with `python -m tfcore.cli pool <iso>`.

Yu-Gi-Oh!, Tag Force and all card names, artwork and characters are trademarks and copyrights of
Konami Holdings Corporation and their respective owners. This project is an unofficial fan tool,
not affiliated with or endorsed by Konami, and is not for commercial use.

## Python libraries (installed with pip, not bundled)

| Library | Licence |
|---|---|
| NiceGUI | MIT |
| FastAPI | MIT |
| Starlette | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| Pydantic, pydantic-core | MIT |
| python-socketio, python-engineio | MIT |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| NumPy | BSD-3-Clause |
| Pillow | MIT-CMU |
| aiohttp | Apache-2.0 AND MIT |
| HTTPX | BSD-3-Clause |
| orjson | MPL-2.0 AND (Apache-2.0 OR MIT) |
| Jinja2 | BSD-3-Clause |
| markdown2 | MIT |
| pytest (tests only) | MIT |

The full list with versions is in `requirements.txt`.

## ogy licence (BSD-2-Clause)

```
Copyright (c) Sten Feldman
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
