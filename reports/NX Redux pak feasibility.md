# TF Deck Studio as an NX Redux pak — feasibility (2026-11-05)

Question: can TF Deck Studio run on the TrimUI Brick (Pro) under NX Redux as a Tools pak, and edit the
Tag Force saves stored on the device itself?

**Answer: yes, as a "server pak".** The pak starts the existing app on the handheld, the handheld's
screen shows its address, and you edit from a phone/PC browser on the same Wi-Fi. Saves are read and
written locally on the SD card; no SSH. A fully on-screen version (D-pad UI, no second device) is
possible but is a rewrite of the UI and not worth it first.

Not verified on the device yet: the Brick did not answer on the network during this research
(switched off or asleep), so everything marked *check* needs one session with the device on.

## 1. What NX Redux allows

- NX Redux is a NextUI (MinUI) fork for Brick, Brick Hammer, Brick Pro, Smart Pro S, Smart Pro.
  ([nx-redux](https://github.com/mohammadsyuhada/nx-redux))
- A tool pak is a folder `<Name>.pak` with a POSIX-sh `launch.sh`, under `Tools/` or
  `Tools/tg5040/` on the SD card; bundled tools win over a user pak of the same name. Launchers get
  `SDCARD_PATH`, `SAVES_PATH`, `USERDATA_PATH`, `LOGS_PATH` etc. The firmware ships no CA store.
  ([PAKS.md](https://github.com/mohammadsyuhada/nx-redux/blob/main/.dev/PAKS.md))
- The maintainer states third-party paks are **not supported** — they work by the same mechanism,
  but a firmware update could break one and nobody upstream will help.
- On-screen UI for shell paks: josegonzalez's `minui-presenter` (show a message), `minui-list`
  (menu) and `minui-keyboard`, prebuilt for tg5040 and used by community paks such as
  [minui-wifi-pak](https://github.com/josegonzalez/minui-wifi-pak). *Check* they draw under NX Redux.

## 2. What the app needs at runtime

| Need | Where it comes from on the Brick |
|---|---|
| Python 3 | Not on the firmware. Ship a portable CPython ([python-build-standalone](https://gregoryszorc.com/docs/python-build-standalone/main/running.html), aarch64, needs glibc ≥ 2.17; the Brick has 2.33). ~100 MB unpacked, less after dropping tests/idle. |
| nicegui + fastapi/uvicorn stack | Pure Python, plus compiled bits (pydantic_core, orjson, httptools…) that all publish manylinux aarch64 wheels. |
| `cryptography` (save AES) | manylinux aarch64 wheel. Could also be replaced by a pure-Python AES: saves are small. |
| numpy + Pillow | Only to decode card art when **building** the catalog from an ISO. Build the catalog on the PC and copy it (56 MB TF6, 75 MB TFSP), so the device needs neither. |
| Card data | The catalog cache folder (`cards.json`, `cardinfo_jpn.ehp`, `art/`). No game data in the pak itself, as now. |
| Saves | Local files: `/mnt/SDCARD/Saves/PSP/SAVEDATA/<ID>` (built-in core) or `/mnt/SDCARD/Saves/.config/ppsspp/PSP/SAVEDATA` (standalone PPSSPP). `tfcore.device.SAVE_ROOTS` already lists both. *Check* which one NX Redux uses now. |

Total pak size: roughly 150–250 MB including both catalogs. SD space is not a concern.

## 3. Memory and speed

- The Brick has 1 GB RAM; under NextUI/NX Redux the launcher is not running while a pak runs, so
  most of it is free (the Smart Pro S showed ~640 MB available at idle with its heavier UI).
- On the PC the running app holds ~590 MB private memory (Windows figure, with art and several
  open pages). On Linux with one browser page the Python process should be far smaller, but this
  is the main unknown: *check* the RSS on the device with one save open. If it is too high, the
  easy wins are: load one game's catalog only, don't keep closed pages' element trees, and serve art
  as files (already the case).
- CPU: 4× Cortex-A53 @ 1.8 GHz is roughly 5–10× slower than the PC per core. Page builds and the
  swap search (`similar()` over ~7k cards) should stay well under a second or two; *check*.

## 4. How it would work

1. `Tools/tg5040/TF Deck Studio.pak/launch.sh`
   - set `HOME`/workspace to `$USERDATA_PATH/TFDeckStudio` (config, drafts, library, backups);
   - start `python/bin/python3 app/main.py --device-local --port 8080` in the background;
   - show `minui-presenter`: "Open http://<wlan0 IP>:8080 on your phone. Press B to stop.";
   - on B: stop the server, `sync`, return to the launcher.
2. App changes (small): a `--device-local` mode that
   - opens the save folders found under `SAVE_ROOTS` directly (no SSH, no device sync panel);
   - uses catalogs copied to the SD card;
   - keeps the existing safety rules: backup before every write, md5 check, `.new` + rename, `sync`.
3. Wi-Fi: the pak only works with Wi-Fi on; *check* that NX Redux keeps Wi-Fi up and the device
   awake while a pak shows a message (the screen may need to stay on).

Safety on the device is simpler than over SSH: while the pak runs, no emulator can be running.
The remaining risk is the same one already noted for spruce: loading a resume/save state taken
before the edit puts the old deck back in memory, and the game may later save that over the edit.
The pak's screen should say "start the game fresh, don't load a save state".

## 5. Options compared

| Option | What you get | Effort | Risk |
|---|---|---|---|
| **A. Server pak** (recommended) | Full current app; phone/PC browser as the screen; local saves | Low–medium: packaging + `--device-local` mode + launcher | Memory unknown; third-party pak unsupported upstream |
| B. On-screen pak | Deck editing with D-pad on the Brick itself, no phone | High: new UI (SDL2 or pygame on KMSDRM/PowerVR), Chinese font, gamepad navigation, keyboard via `minui-keyboard` | GPU/SDL quirks on GE8300; weeks of work |
| C. Stay on PC + SSH sync (today) | Works now, verified on both handhelds | None | Needs the PC on |

A can come later than C without losing anything: the save format code (`tfcore`) is the same.

## 6. To settle with the device on (one session, read-only except copying the pak)

1. `python3 -V` from the portable build runs; `import nicegui, cryptography` works.
2. RSS of the app with one save open and the card browser shown.
3. `minui-presenter` draws a message under NX Redux.
4. Wi-Fi stays up while the pak runs; phone can load the page.
5. Which `SAVEDATA` root the current NX Redux PSP emulator writes.
