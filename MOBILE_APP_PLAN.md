# TF Deck Studio — mobile app plan

Written 2026-10-28. Status: plan only, nothing built yet.

## 1. What "mobile" should mean

| Scenario | Today | Goal |
|---|---|---|
| A. Phone edits decks while the PC runs the app | Works: the NiceGUI page opens on the phone over the LAN, and the editor already has a phone layout (bottom tabs, card sheet) | Install it like an app, with an icon and no browser address bar |
| B. Phone edits the Brick's save over Wi-Fi, no PC | Not possible | Phone pulls the save from the Brick over SSH, edits it, pushes it back with the same safety checks |
| C. Phone edits PPSSPP-for-Android saves on the phone itself | Not possible | Open `PSP/SAVEDATA/<id>` on the phone, edit, and write it back |

B is the main reason for a real app. C uses the same code once storage access works. iOS gets A
only: it has no PSP save folder to open, and installing apps outside the App Store is hard.

## 2. Constraints from the current code

- `tfcore` (~4.7k lines) is plain Python. Its native dependencies are `cryptography` (AES for the
  save crypto), `numpy` + `Pillow` (art decoding, only when the catalog is built), and
  `subprocess` calls to the system `ssh` client (`device.SSHTransport`, `iso.DeviceISO`).
  Android has no `ssh` binary.
- The UI is NiceGUI 3.18 (FastAPI + uvicorn + Vue/Quasar) and is already responsive.
- Workspace size per game: ~55–75 MB catalog (card data + WebP art), 14 MB ygocdb names,
  5 MB TF6 wiki pages. That's fine on a phone, but the art should be built once and copied, not
  decoded on the phone if that turns out to be slow.
- The ISO (1–1.5 GB) is needed only to build a catalog. Building reads a few MB
  (`cardinfo_jpn.ehp`, the CIP art indexes, the TFSP EBOOT), so the phone never has to copy the ISO.
- Rules that still apply: no Konami data ships with the app; the card collection (trunk) stays read-only;
  every write is decrypt → edit → encrypt → verify → back up → push → re-read.

## 3. Options

| Option | How | Reuse | Effort | Verdict |
|---|---|---|---|---|
| 1. PWA over the PC server | Web manifest, icon and service worker for the app shell; phone "installs" the LAN page | 100% | Days | **Do first**, covers A on Android and iOS |
| 2. Android app with embedded Python | Kotlin shell with a WebView; Python (Chaquopy) runs the same NiceGUI server on `127.0.0.1` inside the app | ~95% (`tfcore` + UI); new: SSH transport, file access, small native bridge | 2–4 weeks | **Recommended** for B and C |
| 3. Native rewrite (Kotlin/Compose or Flutter) | Port `tfcore` and rebuild the UI | Logic only as reference | 2–3 months | Better feel, but two code bases to keep in sync. No |
| 4. Offline web app with Pyodide | `tfcore` in WebAssembly in the browser | `tfcore` mostly | Weeks | Android Chrome cannot open a save folder or SSH. No |

BeeWare Briefcase is the fallback for option 2 if Chaquopy cannot build a dependency. The
design is the same: a WebView pointed at an in-process server.

## 4. Recommended design (option 2)

```
Android app (Kotlin, single Activity)
  WebView  ──http://127.0.0.1:<random port>/?token=…──▶  NiceGUI server (Python, Chaquopy)
  NativeBridge (JS interface)                               tfcore (unchanged logic)
    pickFile / pickFolder (SAF)  ──URI──▶  python storage adapter (reads/writes through ContentResolver)
    share sheet, keep-screen-on                             device.ParamikoTransport ──SSH──▶ Brick
```

1. **Server lifetime.** Start uvicorn in a Python thread when the Activity starts; bind
   `127.0.0.1` only, use a random port and a per-launch token cookie so other apps on the phone
   cannot drive it. `reload=False`, no `watchfiles`, no native window.
2. **SSH without a binary.** Add `ParamikoTransport` next to `SSHTransport` with the same methods (`run`, `listdir`,
   `read`, `write`, `md5`, `copy_dir`, `rename`, `sync`), plus a Paramiko version of `iso.DeviceISO` for ranged reads. The key is generated in the app
   (ed25519) and shown once so the user can add it to the Brick's `authorized_keys`, which keeps the
   rule that the app never types a password. Discovery (`device.discover`) uses plain sockets and
   should work unchanged; confirm the Wi-Fi multicast/scan permissions.
3. **Files.** Android storage needs Storage Access Framework URIs instead of paths:
   - ISO: `ACTION_OPEN_DOCUMENT` → a seekable file object over a `ParcelFileDescriptor` →
     `catalog.build` reads ranges as it does today.
   - PPSSPP saves (scenario C): `ACTION_OPEN_DOCUMENT_TREE` on `PSP/SAVEDATA`; `SaveFolder` gets a
     small storage interface (list, read, write-new-then-rename, backup copy) with a local-path
     version (today's code) and a SAF version.
   - The workspace (`TFDS_HOME`) lives in the app's private files directory.
   - Import or export of a whole workspace as a zip lets a PC-built catalog (with art) move to the phone.
4. **UI changes.** Replace the typed-path inputs on the start page with "choose file / folder"
   buttons when the bridge exists; hide the PPSSPP-on-PC shortcuts; use the Android share sheet
   for exported YDK/text. The editor, catalog and doctor dialogs stay as they are.
5. **Build.** Gradle + Chaquopy 17.x plugin, Python 3.13, an explicit pinned requirements list
   installed with `--no-deps` (section 7) plus our own `pydantic-core` wheel. Debug APK is
   side-loaded; no Play Store listing (GPL code, user-supplied game data).

## 5. Phases

| Phase | Work | Done when |
|---|---|---|
| M0 | PWA: manifest, icons, `theme-color`, service worker caching the static shell only | "Add to home screen" opens the editor full screen from the PC server |
| M1 | Refactor without behaviour change: storage interface for `SaveFolder`/`Workspace`, transport factory in `device`/`iso`, `ParamikoTransport` | Full test suite passes; desktop push/pull to the Brick works through Paramiko |
| M2 | Build the `pydantic-core` wheel (section 7); Chaquopy spike: hello-world NiceGUI page in a WebView on the user's phone; import `tfcore` and decrypt a save; measure APK size, cold start, memory | Page loads in < 3 s on the phone; a save decrypts and re-encrypts byte-identical |
| M3 | Scenario B: pull from Brick → edit → push, using a catalog imported from the PC (zip) | A deck saved on the phone loads in Tag Force on the Brick (user tests in person) |
| M4 | Build catalogs on the phone from an ISO picked with SAF (art decode timed; fall back to "import from PC" if too slow) | TF6 and TFSP catalogs built on the phone match the PC's card count |
| M5 | Scenario C: PPSSPP-Android save folder via SAF tree, backups in app storage | Edited save loads in PPSSPP on the phone |
| M6 | Polish: app icon, share sheet, keep-awake during push, error screens, signed release APK | Installed from an APK on a second phone without help |

## 6. Risks and open questions

- **Wheels on Android.** Researched 2026-10-28; see section 7. In short: everything is available
  except `pydantic-core`, which has to be built once. M2 confirms on the phone.
- **APK size** likely 45–70 MB before game data (Chaquopy interpreter alone ~37 MB in a
  third-party spike; numpy ~20 MB unpacked); acceptable for side-loading.
- **SAF write semantics.** No atomic rename across the tree; write `DATA0.new`, verify, then
  replace, and keep the backup copy first. Test with PPSSPP closed.
- **Battery/background.** Android may kill the app in the background mid-push; keep the push in
  the foreground with a wake lock and the existing verify-after-write.
- **Two installs, one workspace.** Phone and PC each keep their own catalogs and backups; the zip
  import/export is the only sync, by design (no cloud).
- **Wi-Fi SSH to the Brick** depends on the Brick's IP (DHCP changes it; discovery already handles
  this on the PC).

## 7. Android package research (2026-10-28)

Checked PyPI's JSON API (files tagged `android_*`), Chaquopy's own package index
(`chaquo.com/pypi-13.1/<package>/`) and two public projects that tried the same stack.

**Chaquopy:** latest 17.2, Python 3.10–3.15, Android API 24+ (Android 7.0). Open source (MIT).

| Package (why we need it) | Android wheel for Python 3.13 | Notes |
|---|---|---|
| `cryptography` (save AES) | Chaquopy: **42.0.8** | Older than desktop (47), but `savecrypto` only uses `Cipher/algorithms/modes`, present in 42. Pin `<43` on Android |
| `numpy` (art decode) | Chaquopy: **1.26.2** | numpy 2.x does not cross-build yet (another project failed six CI attempts). `art.py` uses basic array ops; check it on 1.26 |
| `Pillow` (art → WebP) | Chaquopy: **11.0.0** | Need to confirm WebP encoding is compiled in; serving the PC-built WebP cache does not need Pillow at all |
| `paramiko` 5.1 (SSH to the Brick) | pure Python | Its native deps `bcrypt`, `pynacl`, `cffi` are on Chaquopy for 3.13 |
| `aiohttp`, `markupsafe` | **PyPI** has official `android_24_arm64_v8a` wheels | |
| `multidict`, `yarl`, `frozenlist`, `pyyaml` | Chaquopy | |
| `propcache` (yarl dep) | pure-Python wheel on PyPI | works without its C speedups |
| `orjson` | **none** | NiceGUI lists it as required on arm64, but its code falls back to the built-in `json` when the import fails (`nicegui/json/__init__.py`). Skip it with `--no-deps` |
| `uvicorn[standard]` extras: `httptools`, `uvloop`, `watchfiles` | **none** | Optional at runtime: uvicorn falls back to `h11` + asyncio, and we run without reload. Install plain `uvicorn` with `--no-deps` |
| **`pydantic-core`** (FastAPI → pydantic v2) | **none** (not on PyPI for Android, not on Chaquopy) | **The real blocker.** No pure-Python fallback, and FastAPI cannot run without it |

**pydantic-core plan.** It is Rust (PyO3 + maturin). Another Chaquopy project (otto_android, Sept 2026)
built `pydantic-core`, `jiter` and `orjson` for cp313 `arm64_v8a` + `x86_64` with **cibuildwheel 4.2.1**
on GitHub Actions. It needed no special PyO3 settings, apart from removing each sdist's own
`[tool.cibuildwheel]` table, and the wheels run on a Galaxy S23. A Chaquopy 16.1 / Python 3.12 spike by
someone else failed only because nobody had built these wheels. Termux builds of pydantic-core exist
but target Termux's Python, not Chaquopy, so don't use them.

So: add an M2a step that builds `pydantic-core==<the version our pydantic needs>` (2.50.1 today)
with cibuildwheel for `android_24_arm64_v8a` (+ `x86_64` for the emulator), on GitHub Actions or
WSL with the Android NDK. Put the wheel in `mobile/wheels/` with its SHA-256 and point Chaquopy's
`pip { options "--find-links", ... }` at it. Expect about a day of work, mostly CI setup.
Fallback if that fails: an older FastAPI and NiceGUI pinned to pydantic v1 (pure Python). That
means old, unsupported versions, so treat it as a last resort only.

Other findings:
- Release builds need arm64 libraries aligned to 16 KB pages for Android 15+ devices. cibuildwheel 4.x
  and current Chaquopy produce that; check with `zipalign -c -P 16`.
- `numpy` + OpenBLAS is ~20 MB of the APK. If M4 (building the catalog on the phone) is dropped
  in favour of "import catalog from PC", numpy and Pillow can leave the APK entirely.

Sources: chaquo.com/chaquopy/doc/current/versions.html; PyPI JSON API; chaquo.com/pypi-13.1;
github.com/siddharth23P/otto_android/issues/12; github.com/mdyerapis-coder/assistant-android/pull/1;
github.com/Eutalix/android-pydantic-core; beeware.org/mobile-wheels.
