# Tag Force 6 / Tag Force Special: deck rules, card pools, recipe sources, and reusable local code

Scope: what an AI-built deck must satisfy in Yu-Gi-Oh! 5D's Tag Force 6 (TF6, PSP, 2011) and Yu-Gi-Oh! ARC-V Tag Force Special (TFSP, PSP, 2015); where example decks come from; what the local editor at (this repository) (TF Deck Studio, package `tfcore`) already provides. Local-code facts were read from source and counted with a read-only script run with the project venv on 2026-11-02 against the user's workspace cache (`%LOCALAPPDATA%/TFDeckStudio`). No project files were changed. No device or SSH access was used.

Local sources are cited as `[local: path]`. The project folder is not a git repo, so these are file paths.

## Deck rules and mechanics in TF6 and TFSP (sizes, copy limits, ban list, card types)

### Takeaway
Both games use the same deck-slot format and the same limits: main 40–60, extra up to 15, side up to 15, at most 3 copies across main and extra, further capped by the save's ban list and by the copies the player owns. TF6 defaults to a modified March 2011 OCG list. TFSP defaults to the October 2014 OCG list. Both games have Synchro, Dark Synchro/Dark Tuner (anime cards) and some Xyz monsters. Only TFSP has Pendulum monsters. Contrary to a comment in the local code, TF6 does have Xyz monsters (25 in the game data).

### Cited Findings
- TF6 was released in Japan on 22 Sep 2011 (PSN 26 Jun 2013). By default it uses "an altered form" of the March 2011 OCG lists. — [Yugipedia: Yu-Gi-Oh! 5D's Tag Force 6](https://yugipedia.com/wiki/Yu-Gi-Oh!_5D%27s_Tag_Force_6)
- TF6's default list is the March 2011 OCG list plus several game-original cards. Examples: Forbidden includes Pot of Greed, Graceful Charity, Raigeki, Heavy Storm, Harpie's Feather Duster, Brain Control, Dark Strike Fighter, Goyo Guardian, Thousand-Eyes Restrict, Crush Card Virus, Ring of Destruction; Limited includes Dark Hole, Monster Reborn, Gorz, Tragoedia, Brionac, Trishula, Emergency Teleport, One for One, Call of the Haunted. The page also has Semi-Limited entries. — [Yugipedia: March 2011 Lists (Tag Force 6)](https://yugipedia.com/wiki/March_2011_Lists_(Tag_Force_6))
- TFSP was released in Japan on 22 Jan 2015. By default it uses the October 2014 OCG list. — [Yugipedia: Yu-Gi-Oh! ARC-V Tag Force Special](https://yugipedia.com/wiki/Yu-Gi-Oh!_ARC-V_Tag_Force_Special)
- In earlier Tag Force games (GX Tag Force 2), newer lists could be downloaded, but CPU decks kept their original recipes and ignored the new list. — [Yugipedia: GX Tag Force 2](https://yugipedia.com/wiki/Tag_Force_2) (search snippet)
- Konami ended the PSP data download service for the Tag Force series on 31 Mar 2017. — [YGOrganization](https://ygorganization.com/pspgoawayquickly/) (search snippet)
- The "Destiny Draw" feature stays in TF6, and the TFSP starter decks mark the cards that can be destiny-drawn with "(D)". This is a duel-time feature, not a deck-building rule. — [Yugipedia: TF6](https://yugipedia.com/wiki/Yu-Gi-Oh!_5D%27s_Tag_Force_6); [Yugipedia: Destiny Draw (rule)](https://yugipedia.com/wiki/Destiny_Draw_(rule))
- Size limits enforced by the local save writer: `MAIN_MIN, MAIN_MAX, SIDE_MAX, EXTRA_MAX = 40, 60, 15, 15`. `write_deck` refuses decks outside these limits. The slot holds up to 75 main entries (`MAIN_CAP = 75`), but the rule check uses 60. — [local: tfcore/tf6save.py]
- Copy limit used by the local rule check: copies in main+extra may not exceed `min(3, allowed, owned)`. `allowed` is the save's own ban-list cache in the trunk (2 bits per card row). `owned` is the copies the player holds. The side deck does not count, because the game itself saved a deck with 3 in main and 1 in side. With `banlist=False`, `allowed` is treated as 3. — [local: tfcore/tf6save.py `problems()` and `trunk()`]
- The rule check also requires extra-deck frames (fusion/synchro/xyz/darksynchro) to be in the extra deck and all other cards in the main deck. — [local: tfcore/tf6save.py; tfcore/carddb.py `EXTRA_FRAMES`]
- Both games use the same save deck format: 200 slots of 436 bytes at offset 0x20. Only the plaintext size and the trunk offset differ (TF6 0x29418, TFSP 0x33A24). The layout was verified in-game for both (APP_PLAN 1b5/1b6). — [local: tfcore/games.py; tfcore/tf6save.py; APP_PLAN.md]
- The project's plan says "Tag Force can turn its ban list off" and adds a per-game 禁限卡表 开/关 switch. When it is off, the trunk reports every card as allowed 3. The UI reminds the player to turn the ban list off in the game too. — [local: APP_PLAN.md §1b8c]
- Card-type counts from the game data (local CardDB on the user's Chinese-patched ISOs):
  - TF6: 5,392 cards — effect 2,393, spell 1,020, trap 865, normal 631, fusion 172, synchro 160, token 81, ritual 38, **xyz 25**, darksynchro 7, pendulum 0. 207 Tuners and 7 Dark Tuners.
  - TFSP: 7,254 cards — effect 3,274, spell 1,312, trap 1,101, normal 672, xyz 278, fusion 217, synchro 207, token 95, ritual 52, **pendulum 39**, darksynchro 7. 249 Tuners and 6 Dark Tuners. — [local: tfcore/carddb.py run on cached cardinfo_jpn.ehp]
- TF6's 25 Xyz include Number 39: Utopia, Gem-Knight Pearl, Number 17: Leviathan Dragon and Thunder End Dragon (card numbers 9575–9839). — [local: CardDB output]. Yugipedia confirms: "Includes Xyz Monsters from Yu-Gi-Oh! ZEXAL". — [Yugipedia: TF6](https://yugipedia.com/wiki/Yu-Gi-Oh!_5D%27s_Tag_Force_6)
- TFSP Starter Deck 2 contains Pendulum monsters (Flash Knight, Foucault's Cannon). TFSP Starter Deck 1 has Xyz monsters in its extra deck. — [Yugipedia: TFSP](https://yugipedia.com/wiki/Yu-Gi-Oh!_ARC-V_Tag_Force_Special)
- Local opening-hand math assumes a 5-card hand and no draw for the player going first on turn 1 ("as in the 2011 rules"). — [local: tfcore/doctor.py]

### Inferences
- An AI builder's hard constraints are: 40 ≤ main ≤ 60; extra ≤ 15; side ≤ 15; extra-frame cards only in the extra deck; per card, copies in main+extra ≤ min(3, ban-list allowance from the save, owned copies) (owned can be ignored for "ideal" decks); every card must be in that game's pool. `TF6Save.problems()` already checks all of these and can serve as the final validator.
- The code comments that say TF6 = "2010 card pool (no Xyz)" ([local: tfcore/ygoprodeck.py] `SEARCHES` comment) and that list "extra-deck types the game lacks (Xyz in TF6)" (APP_PLAN §1b8b) are inaccurate. TF6 has 25 Xyz, so a TF6 builder can use Rank 1–5 Xyz (and one Rank 8) but has a very thin Xyz toolbox. Its pool is mid-2011 OCG, not 2010.
- Pendulum mechanics are relevant only for TFSP and only for 39 early cards. TFSP's era (October 2014 list, Secrets of Eternity) suggests Master Rule 3 Pendulum zones, but no source checked here confirms the game's rules version.
- Because ban lists differ by save (and the downloadable lists are gone), the save's trunk cache, not a hard-coded list, is the right source for "allowed" copies. The code already does this.

### Gaps
- No primary source was found (Yugipedia, GameFAQs, YGOrganization searches) that documents the in-game option to turn the ban list off in TF6 or TFSP, or what it is called. The only claim is the project plan's statement. Yugipedia's TF6/TFSP pages could not be fetched through WebFetch (HTTP 403); their wikitext was read through the MediaWiki API instead.
- Whether TF6/TFSP enforce an extra-deck minimum, or allow forbidden cards in the side deck, was not checked in-game. The local code accepts an empty extra and side.
- The Semi-Limited section of the TF6 list was truncated in the fetched excerpt. The full list is on the Yugipedia page. The TFSP list (October 2014 OCG plus any game-original changes) was not fetched.
- The game files contain a ban list (`database/limitlist.ehp`, mentioned in APP_PLAN §8 as a "could" item), but there is no parser for it yet.

## Card pool sizes and documentation of in-game character/CPU and recipe decks

### Takeaway
TF6 has about 5.3–5.4k cards (pool to Photon Shockwave/June 2011, 352 game-only). TFSP has about 7.25k (to Secrets of Eternity/Jan 2015, 396–456 game-only/special). TFSP's 841 built-in recipes, 4 per character plus 73 special decks, are already extracted locally from the ISO. TF6's recipes are not in readable form (encrypted EBOOT), so its character decks come from Yugipedia's 126 TF6 character pages. Those pages have not been downloaded into this workspace yet.

### Cited Findings
- TF6 "includes 5311 cards". The pool goes up to Photon Shockwave, Structure Deck: Devil's Gate, Duel Terminal – Xyz Startup!!, V Jump Edition 5, Premium Pack 13 and Extra Pack Volume 4. — [Yugipedia: TF6](https://yugipedia.com/wiki/Yu-Gi-Oh!_5D%27s_Tag_Force_6)
- TFSP "includes over 7000 cards", up to Booster SP: Tribe Force, Structure Deck: Synchron Extreme and Secrets of Eternity. Unlike earlier games, cards are sold in the real OCG packs and ratios. — [Yugipedia: TFSP](https://yugipedia.com/wiki/Yu-Gi-Oh!_ARC-V_Tag_Force_Special)
- TFSP has every anime-exclusive card from earlier Tag Force games and from ZEXAL World Duel Carnival, and no new exclusives. — [Yugipedia: Yu-Gi-Oh! Tag Force](https://yugipedia.com/wiki/Yu-Gi-Oh!_Tag_Force)
- Local built-in pools: TF6 5,392 card numbers, TFSP 7,254, including tokens and the 2-number duplicates. Game-only cards (passcode 0): TF6 352, TFSP 396. Shipped game-card files: TF6 352 entries, TFSP 456 (game-only plus cards ygocdb lacks). — [local: tfcore/pools/*.json; tfcore/gamecards/*.json; CardDB count]
- Yugipedia character categories: "Yu-Gi-Oh! 5D's Tag Force 6 characters" has 126 pages; "Yu-Gi-Oh! ARC-V Tag Force Special characters" has 192 pages. — [Yugipedia API categoryinfo](https://yugipedia.com/wiki/Category:Yu-Gi-Oh!_5D%27s_Tag_Force_6_characters)
- Yugipedia character pages have per-game {{Decklist}} templates with name, ja_name, a 1–10 star level and card lists by kind. The local `wikidecks.py` parses these. — [local: tfcore/wikidecks.py docstring]
- The project plan estimates about 476 TF6 decks across about 130 character pages, with about 150 containing cards TF6 lacks (anime-only). These are skipped and listed. — [local: APP_PLAN.md §1b8] (the project's own count, not re-verified; `<home>/wiki/TF6_pages.json` does not exist in the current workspace)
- Yugipedia lists TFSP's 3 starter decks and the "Dark Tournament" decks: restored meta decks such as Satellarknight (level 10), Dragon Ruler, Fire Fist, Spellbook, Inzektor, Infernity and Blackwing. The player cannot get their recipes. — [Yugipedia: TFSP](https://yugipedia.com/wiki/Yu-Gi-Oh!_ARC-V_Tag_Force_Special)
- TF6 starts the player with 3 pre-built decks (shown on the page with level 4). — [Yugipedia: TF6](https://yugipedia.com/wiki/Yu-Gi-Oh!_5D%27s_Tag_Force_6)
- TFSP recipes read from the user's ISO (`recipes.json` cache, format 1): **841 recipes** — character 768 (192 characters × 4 levels, Lv1..Lv4), structure 36, starter 9 (STARTER DECK 2006…), pack 7 (Duelist Sets, 決闘王の記憶), repro 6 (再现: Tellarknight, Burgesstoma, Fire Fist, Spellbook, Dragon Ruler, Shaddoll), wcs 6 (WCS 2009–2014 champions), meta 6 (认真!: Qliphort/Lightsworn ("代行天使"), Madolche, HERO, Nekroz, Shaddoll, Qliphort ("机壳")), starter0 3 (initial decks). Main size: 832 recipes have exactly 40, a few have 41–44. Extra up to 15. Only 18 have a side deck. — [local: TFDeckStudio cache NPJH00142-*/recipes.json; tfcore/recipes.py]
- The plan counts 210 TFSP recipes as "champion" (WCS/meta/repro, or a character's Lv4 deck). — [local: APP_PLAN.md §1b8; tfcore/recipes.py `champion`]
- The TF6 ISO cache has `recipes.json` with 0 recipes, because TF6's EBOOT is encrypted and its recipes cannot be read from the ISO. — [local: cache ULJM05940-*/recipes.json; APP_PLAN.md §1b8]
- The plan reports that 202 of TFSP's 841 main decks fit TF6's pool unchanged, including the 2009/2010/2011 WCS champions. — [local: APP_PLAN.md §1b8b]
- In earlier Tag Force games, CPU decks kept their original recipes regardless of downloaded lists, so CPU recipes may break the default ban list. — [Yugipedia: GX Tag Force 2](https://yugipedia.com/wiki/Tag_Force_2) (search snippet)

### Inferences
- For TFSP, the 841 recipes give an in-distribution training/reference set right away: 192 characters × 4 strength tiers plus about 18 meta/WCS decks. The level 1–4 ladder could act as a weak strength label.
- For TF6, an AI builder's main in-game example source is Yugipedia (CC BY-SA 4.0, attribution needed), plus the subset of TFSP recipes that fit TF6's pool.
- The CPU partner/opponent decks stored in the save (APP_PLAN §8 mentions "Partner/CPU deck browser (0x154C0)") are another possible source, but nothing in the code reads them yet.

### Gaps
- GameFAQs guides for TF6/TFSP recipes were not reached (searches returned no GameFAQs pages). Whether a full recipe list for TF6 exists outside Yugipedia is unknown.
- Yugipedia's coverage of TFSP character decks (192 character pages) was not checked deck by deck, and `wikidecks.CATEGORY` only has TF6.
- The exact gap between Yugipedia's 5,311 for TF6 and the local 5,392 is not explained. It is probably tokens (81) and duplicate numbers, but that was not verified.

## Era-appropriate real-world formats and fit to each pool

### Takeaway
Edison (TCG, March 2010 list) and Goat (2005) fit inside both pools. TF6's pool runs to mid-2011 OCG, so 2010–early 2011 decks fit best, and the 2011 World Championship game decks mostly fit. TFSP's pool runs to Jan 2015, so 2011–2014 (Wind-Up, Dragon Ruler, Fire Fist, Spellbook, Tellarknight, Shaddoll, Qliphort, Nekroz) decks fit, and TFSP itself ships several of them as recipes.

### Cited Findings
- Edison Format follows the March 2010 TCG Forbidden/Limited list. — [edisonformat.com banlist](https://edisonformat.com/banlist.html)
- Edison is named after the Shonen Jump Championship in Edison, NJ (24–25 Apr 2010). Goat refers to the format "officially played during the summer of 2005". YGOPRODeck also has categories "World Championship Decks" and "Worlds Format Decks". — [YGOPRODeck Formats](https://ygoprodeck.com/formats/)
- Secondary sources say the Edison pool covers TCG cards up to about April 2010 (ending with Duelist Pack: Kaiba) and uses 2008 rules, where the first player draws. These are secondary and unverified. — [search summary of edisonformat.com / ygoprodeck articles](https://ygoprodeck.com/article/an-introduction-to-sjc-edison-format-93251)
- Project check (2026-10-29): 14 of the first 15 sampled YGOPRODeck Edison decks fit both games completely, and the only missing card was Pole Position. YGOPRODeck "World Championship Decks" has one deck per year from 2003 to 2018. "Tournament Meta Decks" categories are 2023+ and too new. — [local: APP_PLAN.md §1b8b, §1b8h]
- YGOPRODeck's owner declined a deck-download API (GitHub AlanOC91/YGOPRODeck#530, June 2025). The app therefore only opens the site's search and imports YDK files the user exports. — [local: tfcore/ygoprodeck.py docstring; APP_PLAN.md §1b8b]
- Search presets in the app: TF6 → Edison, WC 2010/2009/2008, Goat; TFSP → WC 2014/2013/2012/2011, Edison, Goat. — [local: tfcore/ygoprodeck.py `SEARCHES`]
- TFSP's own WCS champion recipes cover 2009–2014, and its 再现/认真 decks cover 2013–2014 meta archetypes. — [local: recipes.json]

### Inferences
- Since TF6 has Photon Shockwave-era cards, its "native" real format is OCG March–June 2011 (early Xyz, Six Samurai, Agents, Gravekeepers, Plants, Dino Rabbit beginnings). That is a better match than Edison, which is the closest well-documented TCG retro format and which the app already targets.
- TCG-only cards (some promos, TCG-first prints) can be missing from these OCG-based pools. The local `standins.json` (Wiretap → TF6's 陷阱封锁) handles exactly this case.
- Real decks follow real ban lists (TCG March 2010, OCG Oct 2014, and so on). An adapter must re-cap them to the save's list. `similar.align/suggest/fill` already does this.

### Gaps
- No authoritative fit percentages per format were measured beyond the project's 15-deck Edison sample and the 202/841 TFSP→TF6 recipe count.
- I found no curated, licensable dataset of 2011–2014 OCG tournament decklists to bulk-import (YGOPRODeck's data cannot be scraped by policy).

## Local code map: reusable pieces for an AI deck builder

### Takeaway
`tfcore` already provides a full card model with Chinese text and type bits, regex role tags, an in-memory similarity scorer with ban-list fitting (align/suggest/fill), a unified deck catalog (TFSP 841 ISO recipes, TF6 Yugipedia decks on request, YDK imports, the user's library), opening-hand odds plus heuristic advice, a rule validator, and save read/write with device sync. It has no synergy graph, no deck-level scoring, no simulation and no embeddings.

### Cited Findings
- **Card model** `Card(num, row, passcode, name, text, attribute, frame, level, atk, defense, arts, game_only, tuner)`. `frame` is one of normal/effect/fusion/synchro/darksynchro/xyz/ritual/pendulum/token/spell/trap. `level` is the level/rank for monsters and a subtype code for spells/traps. `tuner` is 0 (none), 1 (Tuner) or 2 (Dark Tuner). Helpers: `is_monster`, `extra_deck`. The parser decodes the ISO's `cardinfo_jpn.ehp` (names, Huffman-coded effect text, `$mNNNN` card-name references resolved). Frame, tuner and ATK/DEF decoding were checked against ygocdb on 2026-10-28. Card text is the patched ISO's Chinese text. — [local: tfcore/carddb.py]
- **Card sources** (best first): ISO catalog (names, text, art); ygocdb names download (text, no art); numbers only. Built-in pools (card-number runs) and game-only card JSON make saves readable without an ISO. — [local: tfcore/cardsource.py, pools.py, gamecards.py, workspace.py]
- **Role tags** (`tfcore/tags.py`): 13 keys — staple 通用强卡, tuner, handtrap, gy, sent, negate, summon_react, attack_react, wipe, search, draw, revive, limited. All come from regexes over the Chinese effect text and accept both TF6 and TFSP wording, except staple (158 built-in Konami IDs in `tags_staples.json` plus the user's marks) and limited (save allowance < 3). Text-tag counts: TF6 — sent 398, negate 254, draw 229, tuner 214, search 183, wipe 178, gy 137, revive 125, attack_react 46, handtrap 29, summon_react 24. TFSP — sent 634, negate 399, search 357, draw 308, gy 262, tuner 255, wipe 241, revive 181, attack_react 68, handtrap 63, summon_react 35. — [local: tfcore/tags.py; counts from script]
- **Similarity** (`tfcore/similar.py`, no embeddings, scores all 5–7k cards in memory, about 7–40 ms per query per APP_PLAN):
  - `similar(num, cards, room, limit)` filters to the same kind (main monster / extra monster / spell / trap). Score = 0.55 × text (0.6 × character-bigram Jaccard + 0.4 × character-set Jaccard) + 0.3 × role-tag Jaccard, plus 0.15 for a shared archetype (leading name word or 名字带有「X」), plus small frame/attribute/level or spell/trap-subtype bonuses. Wipes that hit the wrong thing get −0.2 and narrow wipes −0.1. Staples that do the same job sort first. Tuner status is preserved. Results are de-duplicated by name. It returns `(num, score, reasons)`.
  - `align(deck, cards, cap, ok)` trims main+extra to the copy caps and returns the fitted deck and the cuts with options.
  - `suggest(cuts, cap, used)` makes greedy default picks that share the remaining room.
  - `fill(fitted, cuts, picks, cap)` builds the final deck. — [local: tfcore/similar.py; APP_PLAN.md §1b8e]
- **Deck catalog** (`tfcore/deckcatalog.py`): the `Entry` fields are key, name, group, character, level, champion, main, extra, side, missing, source, url. Sources:
  - `from_recipes` (TFSP ISO, 841)
  - `from_wiki` (TF6 Yugipedia, downloaded on request into `<home>/wiki/TF6_pages.json`, resolved through ygocdb English names, stand-ins and user aliases; champion = 9★+)
  - `from_ygoprodeck` (the user's saved YDK imports, passcode → number through card data, built-in alternates (`passcodes_alt.json`, 148 cards) and the cached API konami_id table)
  - `from_library` (我的卡组)
  
  `entries()` merges them per game. — [local: tfcore/deckcatalog.py, recipes.py, wikidecks.py, ygoprodeck.py]
- Current workspace contents: the TFSP recipe cache has 841 recipes. The TF6 recipe cache has 0. There is no wiki download yet. `ygoprodeck/saved.json` has 2 decks ("wc06", "Kfc"). `mydecks.json` has 2 decks ("wc2012", "六武众"). `passcodes_all.json` is present. — [local: %LOCALAPPDATA%/TFDeckStudio]
- **YGOPRODeck import** (`tfcore/ygoprodeck.py`): `from_ydk` (YDK or ydke:// → passcode lists), `passcode_index`, `fit(deck, idx, limit)` → main/extra/side numbers plus missing passcodes plus over-limit entries plus a change count, `PasscodeCache` (one bulk download of the documented card API, `konami_id` = game card number), `Store`. — [local: tfcore/ygoprodeck.py]
- **Text importer** (`tfcore/importer.py`, 456 lines): free-text, YDK and ydke parsing, fuzzy name matching (CN/EN/JA, nicknames.json, aliases), stand-ins, `finish()` returning cuts with swap options, and `to_ydk` / `to_text` export. — [local: tfcore/importer.py function list]
- **Drafts and library** (`tfcore/mydecks.py`): `Drafts` (per-save autosave of unsaved edits with stamps, crash-safe temp-file writes) and `Library` (named decks per game as card numbers, `save/find/remove`). — [local: tfcore/mydecks.py]
- **Analysis** (`tfcore/doctor.py`): exact hypergeometric `p_at_least` and `odds(main, group)` for opening hands and turns 2–3; composition (types, frames, level histogram, Tuner/Dark Tuner counts); rule-of-thumb advice (deck > 40, monster count, no traps, Synchros without Tuners, Dark Synchros without Dark Tuners, Xyz rank vs main levels, fusion/ritual without enablers, 7★+ glut, many singletons). — [local: tfcore/doctor.py; APP_PLAN.md §1b7]
- **Save I/O**: `savecrypto.py` (Tag Force key, verified), `tf6save.py` (`TF6Save.decks()`, `deck(slot)`, `free_slot()`, `write_deck()`, read-only `trunk(row)` → (owned, allowed, flags), `problems()` validator), `savefolder.py`, and `device.py` (pull/push to the handheld with backups and checksum re-read; not used here). — [local: tfcore/*.py]
- **App**: NiceGUI web app `app/main.py` (1,616 lines, port 8080) imports deckcatalog, doctor, importer, mydecks, similar, tags, wikidecks and ygoprodeck. — [local: app/main.py header]
- **Tests**: 18 pytest files with about 95 test functions, including test_similar (10), test_importer (16), test_ygoprodeck (7), test_tf6save (7), test_deckcatalog (3) and test_recipes (3). Fixtures include text imports (battery, dragunity, fate, junk, karakuri, morphtronic). — [local: tests/]
- **Planned but not built**: `tfcore/adapt.py` (shared adaptation with a faithfulness %, archetype fill through ygocdb setcode), an archetype quick-build/upgrade view, a partner/CPU deck browser, a ban-list viewer from `limitlist.ehp`, and "optional AI advice". — [local: APP_PLAN.md §1b7, §1b8b, §8] (no `adapt.py` exists in tfcore/)

### Inferences
- An AI builder could use: `CardSource.cards` as the candidate universe; `tags.tags_of` plus `Card` fields as features; `similar.similar` as a "replacement/neighbor" operator; `align/suggest/fill` as the legality repair step; `TF6Save.problems` as the final validator; `doctor.odds` and the advice as cheap scoring; `deckcatalog.entries` as the example corpus; `Library.save` (or a new slot plus the normal save review) as the output channel.
- The catalog corpus already gives co-occurrence data. TFSP's 841 recipes plus TF6 wiki decks plus imports are enough to build a card co-occurrence/synergy graph, but no code computes one yet.

### Gaps (what an AI builder still lacks)
- No synergy or co-occurrence graph, and no archetype membership table. Archetypes are guessed from name words and 名字带有「X」 text. ygocdb setcodes are planned but not used.
- No deck-level objective or quality score beyond the heuristic advice and hypergeometric odds. No combo/engine modelling (e.g. Synchro level sums are only checked roughly by the doctor).
- No duel simulation or goldfish engine, and no CPU-AI model.
- No text embeddings. Similarity is character-bigram Jaccard over Chinese text only, with no English/Japanese text features.
- No ban-list parser for the game's `limitlist.ehp`. Limits come only from an open save's trunk cache, so building without a save has no ban-list data except the Yugipedia lists.
- TF6 in-game recipes are not extracted (encrypted EBOOT). TF6 wiki decks are not downloaded in the current workspace, and TFSP has no wiki source configured.
- Code comments mislabel TF6 as having no Xyz monsters (see the first section). Any builder logic that drops Xyz for TF6 would be wrong.
