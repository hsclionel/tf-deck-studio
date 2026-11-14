# Tag Force deck editor — app plan

Status 2026-10-27. Companion to `../Tag Force deck editor research.md`, which this plan
supersedes where they disagree.

## 1. What is already proven

Everything below was verified on the user's real saves on the Brick Pro (CN-patched ISOs,
PPSSPP libretro core):

| Fact | Evidence |
|---|---|
| One game key for TF6 and TFSP: `29AF6F5E02F970D52E2412C7E1FC83BA`, crypt mode 5 | Logged by the core on save; both saves decrypt |
| `tfcrypt.py` decrypt/encrypt/file MAC/SFO hashes are exact | Re-encrypting both original saves is byte-identical, MAC and SFO params match |
| TF6 deck layout (0x20, 200 × 436 B) is correct | Rename, new slot, extra-deck edit all load in-game |
| Deck +0x84 timestamp = 6 × u16 (Y M D h m s); +0x90 tag can be a fresh random 20-bit value | New slot with random tag loads without error |
| Card numbers = Konami IDs; `row = IntID[num − 3459]`; trunk at 0x29418 holds owned (bits 8–14) and allowed (bits 0–1 of +2) | Matches ROM rows for every card checked; ban cache shows Stratos/Reinforcement at 1 |
| TFSP plain save is 0x48000, decks at 0x1566C with a different field layout | Decrypted save, starter deck "初期卡组１" found |
| ISO holds card art indexed by card number | `card/cardm_j.cip` (~2 KB/card), `cardh_j.cip` (~4 KB), `cardj_j.cip` (~106 KB); header carries first/last = 3459/9839 then a per-card offset table. Image format inside not decoded yet |
| Alternate artworks are listed in `CARD_SamePict_J.bin` = u16 count + (row, extra-art count) | 44 cards; explains the "因为存在多卡图" banner |

Working scripts in this folder: `tfcrypt.py`, `tfdeck.py`, `carddb.py`, `isofetch.py`;
fixtures in `backups/` (orig → renamed → +元素英雄 → masked swap), deck JSONs in `decks/`.

User rule: **the card collection (trunk) is read-only** unless the user explicitly asks
otherwise. The app may read owned counts and ban limits, never write them by default.

## 1b. Progress (2026-10-27)

- **Data policy (decided):** the app ships no game data. The user provides their ISO and save
  folder; `tfcore.catalog.build` extracts card data and artwork into a local cache once.
- **Phase 0 done:** `tfcore/` package — `iso` (local or SSH), `ehp`, `carddb` (TF6 `_J` and
  TFSP `_R`, frame types incl. xyz/pendulum, effect text), `art` (cardh artwork), `savecrypto`
  (keys embedded, no PPSSPP source needed at runtime), `tf6save` (deck read/write, read-only
  trunk, rule check), `savefolder` (safe write with backup), `catalog`, `cli`.
  `tests/`: 22 pytest tests on the user's own saves and ISOs, including a byte-exact replay of
  the in-game-verified edit chain. Run: `.venv/Scripts/python -m pytest tests -q`.
- Rule found from a game-made deck: the side deck does not count toward the 3-copy limit.
- Mock UI (`app/mock.py`) now reads through `tfcore` like the real app will.
- Old one-off scripts moved to `legacy/`.

## 1b2. Working app (2026-10-27)

`app/main.py` (NiceGUI; `--home DIR --port N`; workspace default %LOCALAPPDATA%\TFDeckStudio):
- Start page: add ISO by path or by scanning a folder; optional ygocdb name download; find saves
  in a save folder or any memory-stick root; recent saves.
- Editor: the approved mock design on real data; a working copy per slot (switching decks keeps
  edits), new decks in free slots, undo, multi-select, rule check, "保存到存档" review dialog
  (renames + per-card diffs, blocks on rule violations) → backup → write → re-read.
- Card sources (`tfcore/cardsource.py`): ISO catalog (full pool, art, owned/ban) › ygocdb names
  (save only: text cards, only cards already in the save's decks can be added) › numbers only.
- Verified end to end on a copy of the memstick: empty workspace → numbers-only → names → ISO →
  rename + add card → save; CLI confirms 10 changed bytes in slot 2 and a byte-exact backup.
- Not yet: text/YDK import & export, partner-deck browser, deleting decks, TFSP editing, packaging.

## 1b3. Built-in card-number lists (decided 2026-10-27)

The one exception to "no game data": `tfcore/pools/TF6.json` and `TFSP.json` (~3 KB each) list
the card numbers each game contains — IDs only, no names, text or images. Trunk row N is the
N-th number of that list, so with them a save alone gives the exact card pool, owned counts, the
save's ban limits and the full rule check. ygocdb supplies names; the game-only cards it lacks
(331 in TF6, 420 in TFSP, all passcode 0, e.g. anime Timelords) show as numbers, sorted last.
Every added ISO is checked against the list (`Catalog.pool_ok`, warning on the start page).

**Game-original cards (decided 2026-10-28):** `tfcore/gamecards/TF6.json` (352 cards, 114 KB) and
`TFSP.json` (456, 143 KB) hold name, type, attribute, level, ATK/DEF and effect text for cards
no outside database describes (passcode 0, or unknown to ygocdb). Taken from the CN-patched ISOs,
so this ships game text (Konami, translated by the patch teams); the user chose this so every card
is fully shown without an ISO. Tests prove every pool card is covered (built-in + ygocdb) and that
the built-in data equals the ISO's. Tiles show a "原创" badge.

Regenerate both with `python -m tfcore.cli pool <iso> --names <ygocdb cards.json>`.

## 1b4. Smart import / export (2026-10-28)

`tfcore/importer.py` + editor dialogs (paste icon = import, share icon = export):
- Input: forum lists (`名字*3`, `3x 名字`, `名字 x3`, full-width), section headers (【怪兽】【魔法】
  【陷阱】【额外】【副卡组】, Main/Extra/Side…), YDK, ydke://.
- Matching against every known name (ROM, ygocdb CN/SC/JP/EN, remembered aliases): exact →
  after dropping notes → attribute shorthand (`命运女郎·光` = the LIGHT 命运女郎) → fuzzy.
  Normalizes Japanese/traditional variants (呪縛牢 = 咒缚牢) and 罪 = Ｓｉｎ. Notes such as
  （黑暗同调） pick the game's anime version. A real name merely contained in a longer query is
  never auto-accepted.
- Adjusts for the game: extra-deck cards routed to extra, copies capped by the save's ban list and
  owned counts; warns when a header's stated count differs from what is listed.
- Review dialog: per-line match with confidence and a candidate dropdown (choices are remembered),
  import as a new deck or replace the current one; nothing is written until "保存到存档".
- Export: forum-style text or YDK (game-original cards, which have no passcode, as comments).
- Found on the way: TF6 encodes anime Dark Synchros as frame code 11 + modifier (`darksynchro`,
  extra deck) and Dark Tuners as code 9 + modifier (main deck); the gamecards files were regenerated.

## 1b5. In-game verification with desktop PPSSPP (2026-10-28)

Desktop PPSSPP 1.20.4 (memstick in OneDrive Documents; `EncryptSave = True`). Test A passed:
the app imported the 命运女郎 forum list as a new deck in slot 4 of the user's TF6 save and wrote
it (backup → encrypt → verify; 121 bytes changed, slot 4 only); the game loaded it, the deck was
correct and playable. This is the first save written end to end by the app rather than by scripts.
Still open: re-reading a save the game wrote after an app write (needs one in-game save).

## 1b6. Device sync with the Brick (2026-10-28) — verified on hardware

`tfcore/device.py` + start page ④ + editor auto-push. Discovery found the Brick at a new DHCP
address (192.168.0.2) in ~6 s; pull → import 命运女郎 into slot 4 → push with all checks (no game
running, device save unchanged since pull, device-side backup in `SAVEDATA_backup/`, .new + mv,
sync, MD5 re-read). The user loaded it in Tag Force 6 on the Brick: works. TFSP layout was also
mapped and verified in-game on desktop PPSSPP the same day (decks at 0x20 like TF6, trunk 0x33A24).

## 1b7. Deck doctor + odds (2026-10-28) — on demand only

`tfcore/doctor.py`: exact hypergeometric odds (first player skips the turn-1 draw), composition
(types, frames, level histogram, extra by frame, Tuner / Dark Tuner counts) and transparent
rule-of-thumb advice (deck > 40, monster count, no traps, synchros without tuners, Dark Synchros
without ＤＴ, Xyz rank vs main-deck levels, fusion/ritual without enablers, 7★+ glut, many
singletons). Tuner flag decoded from CARD_Prop (codes (1,1) (7,1) (31,0) (29,1); (9,1) = ＤＴ),
also carried in gamecards JSON and ygocdb cards. Save-only decks without type data just say the
stats are incomplete. UI: the `insights` button in the deck action bar opens a dialog with tabs
概览 / 上手率 (per-card table + multi-card group calculator) / 建议; nothing shows unless asked.

Next candidates (user's wishlist): archetype view with upgrade
suggestions (ygocdb setcode), ban-list replacement suggestions, online deck search feeding the
importer, optional AI advice; plus deck delete/duplicate, partner-deck browser, packaging.

## 1b8. Deck catalog (卡组库, 2026-10-28)

`tfcore/deckcatalog.py` turns two sources into one `Entry` list (name, group, character, level,
champion flag, main/extra/side, missing cards, source link):

- **TFSP: the game's own 841 recipes** from the user's ISO (`tfcore/recipes.py`, cached as
  `recipes.json` in the ISO catalog). Champion = WCS / 认真卡组 / 再现卡组 / a character's Lv4 deck (210).
- **TF6: Yugipedia character decks** (CC BY-SA). TF6's EBOOT is encrypted, so its recipes cannot be
  read from the ISO. The user downloads ~130 character pages on request into `<home>/wiki/TF6_pages.json`
  (raw wikitext). They are matched to card numbers on each open through the ygocdb English names and
  the user's import aliases, so better name data improves matching without a new download. Of ~476
  decks, ~150 have cards TF6 does not have (anime-only cards); those are skipped and listed.
  Champion = 9★ or more.

UI: `library_books` button in the deck action bar → dialog with search (deck or character),
category filter and a 冠军级 switch → preview (card grid, legality from the save's ban list,
"collection lacks N cards" when the trunk is mapped, skipped cards, source link) → load into a new
slot or replace the current one. Loading only changes the editor; the normal 保存 review writes
the save. The save button label is now just 保存 (tooltip 保存到存档) so the action bar fits.

## 1b8b. Deck catalog v2: real tournament decks, adapted (plan, 2026-10-29)

Tag Force follows the OCG card pool plus game originals, so real decks of the same era fit well
after small changes. Sources, checked 2026-10-29:

| Source | Era | Fit (no changes needed) |
|---|---|---|
| TFSP's own recipes (ISO), shown in TF6 | 2009–2014 | 202 of 841 main decks fit TF6's pool; WCS 2009/2010/2011 champions fit completely |
| YGOPRODeck "Edison Format" (TCG list of 2010, same era as TF6) | 2010 | 14 of the first 15 sampled fit both games completely (only 杆位 / Pole Position missing). 400+ decks |
| YGOPRODeck "World Championship Decks" (the WC video-game decks) | 2003–2019 | 17 decks |
| YGOPRODeck "Tournament Meta Decks (OCG / Worlds / OCG-CN)" | 2023+ only | Too new for either game; skip |

**Decided 2026-10-29: the app does not download decks from YGOPRODeck.** Its public API
(`db.ygoprodeck.com/api/v7`) has no deck endpoint, and the owner declined one (GitHub
AlanOC91/YGOPRODeck#530, June 2025: deck data is curated for viewing on the site). The site's
internal search (`/api/decks/getDecks.php`) is not used. Built instead (`tfcore/ygoprodeck.py`,
catalog dialog tab 「从 YGOPRODeck 导入」): links that open the site's own deck search with the right
category for the open game (`deck-search/?_sft_category=…`; TF6: Edison, World Championship, Goat;
TFSP: World Championship, Edison, Goat), steps (deck page → More... → Download YDK / YDKE), then
a `.ydk` file picker or paste box (plus a deck name; no source-link field, by request) → fit check against the game's cards (stand-ins applied) and the
save's ban list → load into the editor or 保存到卡组库 (`<home>/ygoprodeck/saved.json`, passcodes,
shared by both games; listed in the catalog under "YGOPRODeck").

Adaptation step `tfcore/adapt.py` (shared by every source): deck (passcodes, numbers or text) +
target game + open save's ban list → adapted deck, change list ("原卡 → 替换卡（理由）") and
faithfulness %. Rules in order: stand-ins table; copies over the save's limit → fill from the deck's
own same-role cards, then same-role staples; missing cards → same archetype (ygocdb setcode), then
role tag + type/attribute/level; extra-deck types the game lacks (Xyz in TF6) → drop and fill with
summonable Synchros or leave empty; final legality check. Catalog shows an 改编 badge, the
change list in the preview, and a default filter of ≥ 85 % unchanged.

## 1b8c. Ban-list switch (2026-10-29)

Tag Force can turn its ban list off. The editor's 「禁限卡表 开/关」 chip (next to 合规) sets the
per-game workspace setting `banlist[game]` (default on). Off: `Session.trunk` reports every card as
allowed 3, `TF6Save.problems(banlist=False)` skips ban-list caps (owned counts and the 3-copy rule
still apply), limit badges and the 禁限卡 filter disappear, and the importer and catalog fit check
follow. The tooltip reminds the player to turn the ban list off in the game too.

## 1b8d. Other passcodes of a card (2026-10-29)

A real card can have several passcodes (reprints, alternate artwork): 83011277 and 83011278 are both
Mystic Tomato, #4930. The card data lists one, so an imported YDK could report "not found". The
game's card number equals the `konami_id` that YGOPRODeck's documented card API returns, so
`ygoprodeck.PasscodeCache` resolves it exactly: the first unknown passcode downloads the whole table
once (`cardinfo.php?misc=yes`, 3.4 MB gzip, 14.5k cards, 1.3 s, stored as
`<home>/ygoprodeck/passcodes_all.json`, 270 KB), after which imports are offline (72 ms). Passcodes
newer than that download are asked in small batches and remembered in `passcodes.json`; offline, the
small query is tried and otherwise the line stays "not in this game". Used by the text-import
dialog, the YDK tab, and saved YGOPRODeck decks.

Built-in map (2026-10-29): only 148 cards in TF6/TFSP have an alternate passcode (86 differ from the
main one by exactly 1, nearly all within 7), so they ship as `tfcore/passcodes_alt.json` (3 KB,
numbers only, like the card-number lists; `cli passcodes <passcodes_all.json> --names cards.json`
regenerates it). These resolve offline from the first import; the API table is only for anything
newer.

## 1b8e. Swap cards the ban list cuts (2026-10-29)

`importer.finish` now also returns `cuts` [(num, section, copies lost, why)]. In the import dialog
each cut gets 「换成…」, which lists cards with a similar effect that still have room (ban list,
owned count, copies already in the import); picking one adds it as its own （替换） line, so it shows,
can be changed or skipped like any line, and the cut reads 「已换成…」. Scoring is
`tfcore/similar.py`, in memory, no vector database (5–7k cards per game, 7–40 ms per query):
same card kind (main/extra monster, spell, trap), effect-text character-bigram Jaccard (0.55),
role-tag Jaccard (0.3), shared archetype (name word or 名字带有「X」, +0.15), frame/attribute/level
or spell/trap subtype. Checked: Mirror Force → other attack-reaction wipes, Graceful Charity →
draw spells, Raigeki → 黑洞, Effect Veiler → hand traps, 六武众的影武者 → 六武众 cards.

**Deck library / YGOPRODeck path (2026-10-30).** The catalog preview (recipes, wiki decks, YDK
imports) used to load decks as listed and only warn. Now `similar.align` trims main+extra to this
game's ban list (min(3, allowed); 3 with the ban-list switch off; side deck untouched) and finds
options per cut, `similar.suggest` pre-picks the best option that still has room (picks share room,
so two cuts never both claim the last copy of a card), and `similar.fill` builds the deck that
载入 puts in the editor. The preview shows a switch 「按本游戏禁限卡表调整（N 张超限）」 (on by
default; off loads as listed) and one select per cut: the pre-picked swap, the other options, or
「只删掉，不补」. Chips, rule check and card list show the adjusted deck. Owned shortages are not
swapped here (on a fresh save that would replace most of a deck); they stay in the 收藏缺 chip.

**Scoring fixes (2026-10-30), from 雷击 suggesting 封魔一闪 / 除虫网 instead of 闪电旋涡.**
(1) The 全场破坏 tag missed TF6's word order 「对方场上存在的全部怪兽破坏」 (雷击, 黑洞, 封魔一闪), so
those cards had no role tags at all. (2) Text similarity is now 0.6 bigram + 0.4 character-set
Jaccard with 存在 stripped, so TF6 and TFSP wordings of one effect still match. (3) Mass removal
that hits the other thing (monsters vs spells/traps, e.g. Harpie's Feather Duster for Raigeki) −0.2;
a wipe limited to one type/attribute (永远的渴水, 战士抹杀) −0.1 when the base is not. (4) Built-in
staples +0.1 with reason 通用强卡 — the tie-breaker real decks need: 闪电旋涡 over 封魔一闪 (needs five
monsters), 贪欲之壶 for 强欲之壶, 龙卷 for 旋风. (5) Options are de-duplicated by name (TFSP lists some
cards under two numbers). Lightning Storm (闪电风暴, 2020) exists in neither game.

**Staples first; paste import pre-picks too (2026-10-30).** Instead of a +0.1 bonus, a built-in
staple now sorts ahead of every non-staple when it does the same job: not off-target (other wipe
kind / one-type wipe), the base's archetype if the base has one, and shared roles ≥ half of both
cards' roles together (or text ≥ 0.35). That keeps 雷王 (whose text only forbids searching) away from
三眼怪, and 六武众 cards ahead of staples for 六武众的影武者. The paste-text import now pre-picks a swap
for every cut like the library does; each cut row reads 「雷击」×1（禁止卡） → 闪电旋涡 ×1 〔换别的〕, and
换别的 removes that swap line and shows the options plus 只删掉，不补. Its caps still include owned
copies, so a card you own fewer of (黑森林的魔女 limited in TF6) is not offered beyond what you hold.

**Tuners (2026-10-30).** `Card.tuner` (1 Tuner, 2 Dark Tuner) was only used by the deck analysis.
Now: a 调整 / 黑暗调整 badge on tiles, 【效果／调整】 in the card detail, a 调整 filter chip (tag
`tuner`, from the card type, covers both). Swaps keep the deck's Tuner count: same tuner value
first (Tuner ↔ Tuner, Dark ↔ Dark, non-Tuner ↔ non-Tuner), with reason 调整; other cards only after
them. Because an archetype may have a single Tuner (六武众的影武者 in TF6), the best two
same-archetype cards of the other kind are kept at the end of the list, so the player chooses
between the synchro count and the archetype; 影武者's default is 紫炎的寄子 (a Tuner that is
also 六武众 support). Tuner is kept out of the role-tag Jaccard so it is not counted twice.

## 1b8h. YGOPRODeck suggestions per game (2026-11-01)

The site's deck categories were checked: "World Championship Decks" holds one deck per year
2003–2018 ("World Championship <year> Deck"), and the search page reads `name=` from the URL into
its deck-name filter, so a year opens exactly that deck. "Worlds Format Decks" is mostly modern
and the date filter starts at 2016, so neither is used. Links now: **TF6** — Edison (2010), WC
2010/2009/2008, Goat; **TFSP** — WC 2014/2013/2012/2011, Edison, Goat. `SEARCHES` entries are
(label, category, name filter, hint). Also fixed: clearing a clearable search box sends `None`,
which emptied the deck-library list and would have broken the save-path 查找.


## 1b8i. Browser filters and monster types (2026-11-04)

- **Monster type (种族)** decoded from CARD_Prop f2: bits 1-5 on TF6, 2-6 on TFSP (`carddb.RACES_TF6/RACES_TFSP`;
  TFSP inserts 幻龙 at 22). Matches ygocdb `race` for every listed monster in both games (tokens excepted:
  their type varies). Also filled from ygocdb for the no-ISO card source and added to the built-in
  gamecards JSON. Shown in the card detail type line: 【龙族／同调／调整】.
- **Browser chips**: ♥ 喜欢 (favourites, `config['favorites']`, global since card numbers are shared by both
  games; toggle in the card detail, ♥ badge on tiles), 融合 / 同调 (incl. 黑暗同调) / 超量 (OR among themselves,
  AND with role tags). Kept out of `tags.TAGS` so swap scoring is unchanged.
- **星级 select**: 1–4, 5–6, 7+, or one exact level 1–12; Xyz counts by rank. Spells/traps drop out when set.
- Checked on TF6: 超量 25, 同调+超量 192, 7+ among those 100 (same as the card data).
## 1b8g. Drafts and 我的卡组 (2026-10-31)

Edits used to live only in the page (`st['work']`), so a reload lost them. `tfcore/mydecks.py`:

- **Drafts** — `<home>/drafts/<sha1(save path)>.json`, rewritten (temp file + replace) from
  `refresh_all()` and the name field whenever the unsaved decks change; removed when nothing is
  unsaved (after 保存, or after the user drops the edits). Each draft deck keeps the save deck's
  stamp it started from. Reopening the save puts the decks back and shows a notice
  「恢复了上次没保存的改动：#0「…」」 with 丢掉 / 知道了; a deck the game changed since is named in
  red. Draft decks that already match the save are skipped. Every changed deck in the drawer has a
  还原 button (confirm; 撤销 still brings it back). The drawer title is now 存档里的卡组 so it does
  not clash with the library.
- **我的卡组 (Library)** — `<home>/mydecks.json`, per game, card numbers, replaced by same name.
  Deck toolbar button 「存到我的卡组」; the catalog lists them first in group 我的卡组 (with the ban-list
  fit like any catalog deck) and the preview has 「从我的卡组删除」. Load into any save of the same
  game, then 保存 writes the save and, for a save read from a handheld, writes it back.
  Shown only for the game it was saved from (game-original card numbers differ between games).

## 1b8f. Chinese UI wording pass (2026-10-29)

Rules taken from two Chinese "去 AI 味" skills, read as reference (not installed):
op7418/Humanizer-zh (21k★) and LifelongLazyLearner/qu-ai-wei (704★, pattern catalog). Both target
prose; the subset used for UI microcopy: no essay-style lead-ins or stage directions; plain verbs
instead of 进行/实现 + noun; grammar instead of chains of brackets and colons; no stacked 的 or
English-style long modifiers; short conventional app wording; one term per idea. 99 strings were
rewritten in `app/main.py`, `app/theme.py`, `tfcore/doctor.py`, `tfcore/importer.py`,
`tfcore/ygoprodeck.py`. Terms made consistent: 卡名库 (not 卡名数据库), 持有 (not 拥有), 读取 / 写回掌机
(not git-style 拉取 / 推送), 保存 (the button's actual label). The library's English rule-check
messages (`main deck has 5 cards (40–60)`, `X ×2, limit 1 (ban list 1, owned 9)`) are shown in
Chinese through `problem_zh` in the app; the library keeps English for the CLI and tests.

## 1b9. Role filter (功能筛选, 2026-10-28)

`tfcore/tags.py`: chips under the card browser's type row, combined with AND (e.g. 通用强卡 + 手坑):
通用强卡, 手坑, 墓地发动, 送墓触发, 无效, 召唤反应坑, 攻击反应坑, 全场破坏, 检索, 抽卡, 苏生, 禁限卡.
All except 通用强卡 and 禁限卡 come from regexes over the card's Chinese effect text. They accept both
TF6's older wording and TFSP's ①② wording. A hand trap is a monster that pays its own cost from the
hand at a time the opponent controls, or special summons itself from the hand during battle
(Gorz, Battle Fader); field-condition summons like Cyber Dinosaur / Chaos Hunter are excluded.
TFSP finds 63 hand traps, TF6 29. 通用强卡 = built-in `tfcore/tags_staples.json` (158 well-known staples of the
era, Konami IDs only) plus the user's marks: the detail panel's 标为强卡 / 取消强卡 button, stored in
workspace config `staples[game] = {add, remove}`. 禁限卡 = the save's ban list (allowed < 3).

## 1c. Game and version handling (`tfcore/identify.py`)

| Question | Answered by | Notes |
|---|---|---|
| Which game is this ISO? | `PSP_GAME/PARAM.SFO` `DISC_ID` | ULJM05940 / NPJH50794 → TF6, NPJH00142 → TFSP; anything else is refused |
| Which game is this save? | Folder name prefix, else `SAVEDATA_DIRECTORY` in its PARAM.SFO | Also checks DATA0 size (0x47000/0x48000, +16 when encrypted) |
| Disc revision | `DISC_VERSION` (both user ISOs: 1.01) | Shown, not used for logic |
| Patch language | Script of the card names (+ Chinese font `zh_gb.pgf`) | Patches keep the Japanese disc ID and title, so the SFO cannot tell |
| Which data layout? | Game family (TF6 / TFSP) | Card DB members `_J` vs `_R`, Prop bit shift, save size and deck layout |
| Does this ISO fit this save? | Same family | Card numbers are Konami IDs shared by every patch, so a JP, EN or CN ISO of the same game all work with any save of that game |

App flow: the user adds ISOs once (each becomes a cached catalog keyed by
`<DISC_ID>-<cardinfo md5>`, so JP and CN copies of one game live side by side); opening a save
picks the catalog of the same family automatically, preferring the user's chosen display
language; an ISO/save mismatch is refused with a clear message. A save with no matching catalog
can still be opened (deck list by card number) with a prompt to add the ISO. TFSP saves are
read-only until their deck layout is mapped.

## 2. Decisions to make

| # | Question | Recommendation |
|---|---|---|
| D1 | Stack | **Decided 2026-10-27: Python core + NiceGUI 3.18** (`nicegui==3.18.0`, Python 3.13). The UI is written in Python but renders as a web page (Vue 3 + Quasar components + Tailwind), runs on FastAPI, opens in a native window (`ui.run(native=True)` via pywebview 6.2) or in any browser on the LAN, so the phone works too. Chosen over Flet 1.0 (Flutter; its web build draws on a canvas and needs bundled CJK fonts) and Reflex 0.10 (compiles to React, needs a Node/bun build step). Package with PyInstaller. |
| D2 | Audience | Personal first. If shared publicly later, the crypto is GPL-derived (PPSSPP), so the app is GPL-3.0, and it must ship **no** Konami data: everything is built from the user's own ISO. |
| D3 | Where it runs | Windows PC talking to the Brick over SSH (as today). Also accept a local save folder (desktop PPSSPP, a copied SD card). The UI can be opened from a phone on the same LAN for free since it is a web page. |
| D4 | UI language | Chinese and English UI strings; card names follow a display toggle (ROM / official SC / EN / JP). |

## 3. Architecture

```
tfcore/            pure library, no UI, fully unit-tested
  iso.py           ISO9660 reader over a local file or SSH (dd ranges)  ← isofetch.py
  ehp.py           EHP container
  carddb.py        Indx/Name/Prop/Pass/IntID/SamePict/Genre, Huffman descriptions
  art.py           CIP index + image decode → PNG cache
  savecrypto.py    ← tfcrypt.py
  tf6save.py       typed views: deck slots, partner decks, trunk (read-only), flags
  tfspsave.py      after layout mapping (phase 6)
  catalog.py       SQLite catalog: ROM rows + external names + aliases + art paths
  importer.py      text/YDK/ydke parsing and fuzzy matching
  device.py        Brick discovery, pull/push, safety checks, backups
app/
  main.py          NiceGUI entry: ui.run(native=True) or LAN browser mode
  pages/           browser, deck editor, slots, import, device (NiceGUI components)
  static/          art cache served as files, small custom CSS/JS (drag and drop)
cli.py             same operations headless (also the test harness)
```

Rule kept from today's work: every write goes **decrypt → edit typed view → diff → encrypt →
verify round-trip → back up → push → re-read md5**, and the diff is shown before pushing.

## 4. Card data: preload, mapping, lookup

**Build once, cache forever.** First run reads `cardinfo_jpn.ehp` (730 KB) and the CIP
indexes from the ISO, locally or over SSH with ranged `dd` reads (no need to copy 1.3 GB).
The catalog is cached in SQLite keyed by the EHP md5, so later starts are instant and offline.

**ID mapping table** (one row per card):

| Column | Source |
|---|---|
| `num` (Konami id, the deck value) | `CARD_Prop` |
| `row` (trunk index) | `CARD_IntID` |
| `passcode` (YDK) | `CARD_Pass` (0 = game-only card) |
| `name_rom` | `CARD_Name_J` of this ISO (CN on the user's copy) |
| `name_sc`, `name_en`, `name_jp`, `name_cn_ygopro` | ygocdb `cards.json`, joined on `cid = num`; downloaded and cached, never bundled |
| kind, attribute, race, level, ATK, DEF | `CARD_Prop` |
| frame type (normal/effect/fusion/synchro/ritual/tuner…) | `CARD_Prop` f1 low 5 bits look like a frame code (1 normal, 3 effect, 5/7 fusion, 9/11 ritual, 21 token; others such as 13 toon, 15 spirit/Xyz-like, 17 union, 19 flip still to name) and bit 5 marks synchro/tuner — inferred from the card list on 2026-10-27, used by the mock; confirm against ygocdb types |
| description | `CARD_Desc` + Huffman + `DICT` (port ogy's decoder) |
| alt-art count | `CARD_SamePict_J` |
| pinyin, pinyin initials, normalized keys | computed |
| owned, allowed | the open save's trunk (read-only) |

**Lookup.** ~5,400 rows, so an in-memory index answers every keystroke in under a
millisecond: substring over all name fields, pinyin initials (`qybl` → 青眼白龙),
normalized keys (full-width → half-width, strip `·－- 　`, simplified ↔ traditional), plus
filters: kind, attribute, race, level/rank, ATK/DEF range, frame type, archetype, owned,
ban status, in-current-deck, has alt art.

**Card art.** Decode `cardm` (thumbnails) for the grid at catalog build time; decode
`cardj` (full art) lazily when a card is opened. Cache PNGs on disk. No network needed.
Fallback if decoding stalls: ygocdb/YGOPRODeck images by passcode, cached and rate-limited.

## 5. GUI

Three-pane deck editor, keyboard-first:

1. **Card browser** (left): search box + filter chips, card grid with art thumbnails,
   owned/limit badges, alt-art marker. Enter or double-click adds to the deck.
2. **Deck** (centre): main / extra / side sections in the game's sort order, count bars
   (40–60 / 15 / 15), live validation messages, drag between sections, +/− per card,
   right-click "replace with…" (shows same-archetype candidates).
3. **Detail** (right): full art, ROM name + official names, stats, description, ban status,
   owned, which of the user's decks use it.

Plus a **slot list** (200 slots: create, duplicate, rename, delete, reorder, copy a partner/CPU
deck into a slot) and a **device bar** (connection, game-running state, pending changes,
"Review & push").

## 6. Smart text import

Input: paste or drop a file. Formats, auto-detected:

- YDK (`#main` / `#extra` / `!side`, passcodes) and `ydke://` URLs
- YGOPRODeck / Duelingbook text exports, "3x Name", "Name x3", "Name ×3", "Name*3", "3 Name"
- Chinese forum lists: section headers 怪兽 / 魔法 / 陷阱 / 额外 / 副卡组, full-width digits,
  bullets, table pastes

Pipeline:

1. Split sections and counts.
2. Resolve each name: exact normalized match → alias table (`E·HERO` = `E-HERO` = `元素英雄`
   = `Elemental HERO`) → fuzzy (trigram + edit distance) across every language column,
   with a confidence score.
3. Review screen: green = sure, amber = pick from top 3, red = not found / not in TF6.
   Resolutions the user makes are remembered as new aliases.
4. Post-process automatically, each step shown and undoable:
   route extra-deck types to Extra; cap by ban list (Stratos 3 → 1, as today); cap by
   owned; replace cards missing from TF6 with suggestions; keep 40–60.

Export: YDK, ydke, plain text (any display language), and a deck image (grid of ROM art)
for posting.

## 7. Device sync and safety

- Discover the Brick: scan the /24 for port 22, confirm `TinaLinux` (its IP moved .6 → .12).
- Refuse to write while `minarch.elf` runs.
- Compare md5 with the last read; refuse if the save changed since (the user saved in-game).
- Timestamped backup on device (`SAVEDATA_backup/`) and locally before every push;
  restore from a version list with a diff of which decks changed.
- Write `.new` then `mv`, `sync`, re-read md5.
- Warn that resuming a save state restores the old save into memory and the game will then
  overwrite the edit; offer to start the game without the auto state.

## 8. Feature brainstorm

**Must** (MVP): catalog + search, deck editor with validation, slot management, device
sync with backups, YDK + text import/export.

**Should**:
- Opening-hand odds (hypergeometric: P(≥1 of these N cards in 5/6)) and a test-hand
  simulator.
- Deck stats: type split, level curve, attributes.
- Archetype quick-build: pick 元素英雄 / 六武众 / 剑斗兽 …, see every member in the TF6 pool,
  start from a template.
- "Upgrade" suggestions like today's Masked HERO swap: same-archetype support that exists in
  TF6 but is not in the deck.
- Partner/CPU deck browser (0x154C0) with "copy to my slots" (read-only on the partner side).
- Deck history and diff from the backup chain; export-all-decks to YDK as a readable backup.
- Dry-run review before every push (already the habit).

**Could**:
- TF6 → TFSP deck transfer (same Konami IDs; flag cards outside TFSP's pool) once TFSP is mapped.
- Screenshot import: identify cards in a deck screenshot by perceptual hash against the ROM art.
- Shareable deck code / QR.
- Pack membership ("where do I get this card") from `shop/all_j.ehp` and the shop PRX.
- Ban-list viewer from `database/limitlist.ehp` (view only; changing the save's cache is a
  trunk edit and stays off).
- A small NextUI pak to list backups and restore one without a PC.

## 9. Phases

| Phase | Deliverable | Exit test |
|---|---|---|
| 0. Core hardening | `tfcore` package from today's scripts; pytest suite on `backups/` | Every fixture round-trips byte-exact; slot reads match in-game results |
| 1. Catalog | ISO reader (local + SSH), card table, ygocdb join, frame-type bits, descriptions, search | 4007/4844/7734 spot checks; search by CN, EN, pinyin initials |
| 2. Card art | CIP index + image decoder, thumbnail cache | Thumbnails for all 5,392 cards; full art on demand |
| 3. GUI MVP | Browser + deck editor + slot list on a local save | Build 元素英雄 in the GUI; it loads in-game |
| 4. Device sync | Discovery, safety checks, backups, restore | Edit → push → in-game check → restore works |
| 5. Import/export | Parser, matcher, review screen, post-processing | Today's YGOPRODeck HERO list imports to the same 40/15 deck automatically |
| 6. TFSP | Map the TFSP save layout by diffing in-game edits; enable editing | A TFSP deck edit loads in-game |
| 7. Extras | Section 8 "should" items | — |

## 10. Risks and unknowns

- CIP image format is unknown (likely GIM or compressed blocks); budget a short RE spike.
- `CARD_Prop` frame-type bits are undocumented; the ygocdb correlation should settle them.
- Behaviour with decks holding unowned or over-limit cards is untested; enforce limits until tested.
- The deck +0x098 field and the 62 trailing bytes are unknown; keep preserving them.
- The TFSP layout is unmapped; keep TFSP read-only until phase 6.
- ygocdb has no stated licence and an unstable v0 API: cache it, never bundle it.
