# LLM-Based Deck Building Under a Fixed Card Database and Rules

Research date: 2026-11-02. Older findings are tagged with their dates. Context: the target is a Tag Force (Yu-Gi-Oh! PSP) deck editor with a frozen card pool, card text in Chinese/Japanese, and a handful of example deck recipes.

## 1. Published experiments and projects: how good were LLM-built decks, and how did they fail?

### Takeaway
No rigorous published benchmark tests frontier LLMs building full constructed decks (Yu-Gi-Oh!, MTG, Hearthstone, Pokémon) from a fixed database. The evidence that exists comes from MTG drafting and synergy papers, one MTG Commander pipeline, and practitioner reports. They agree on the main problem: ungrounded LLMs invent or misdescribe cards, get deck counts wrong, and pick weakly. LLMs are much better at narrowing or re-ranking a candidate pool that comes from real data than at building a deck from memory.

### Cited Findings
- **UrzaGPT (arXiv 2508.08382, Aug 2025), MTG draft picks:**
  - Zero-shot GPT-4o picked the same card as human drafters 43% of the time with card names only, against a 22.1% random baseline.
  - Supplying full card text lowered accuracy to 38%. The authors suspect the extra text diluted the prompt.
  - Small 7–8B open models often failed to follow the prompt, picked cards that were not offered, and scored worse than random.
  - LoRA fine-tuning on 1M human picks (17lands, one set) raised Llama-3-8B to 66.2% and Mistral-7B to 64.3%. A domain-specific non-LLM model scored 68%.
  - Limitations: evaluation is single-pick agreement with humans, not final deck quality, and only one expansion was tested.
  - [UrzaGPT, arXiv 2508.08382](https://arxiv.org/html/2508.08382v1)
- **"Rule Synergy Analysis using LLMs" (Bateni, Pratt, Whitehead; arXiv 2508.19484, Aug 2025):**
  - Builds a dataset of Slay the Spire card pairs labelled positive, negative or neutral synergy.
  - LLMs "excel at identifying non-synergistic pairs" but struggle with positive and especially negative synergies.
  - Common errors involve timing, defining game states, and following game rules.
  - [arXiv abstract 2508.19484](https://arxiv.org/abs/2508.19484)
  - I could not extract the per-model numbers from the PDF; see Gaps.
- **EDH-LLM (MTG Commander; project page, undated, GPT-3.5-era):**
  - Pipeline: Word2Vec card-text embeddings plus hand-crafted feature vectors rank cards by similarity to the commander. The two rankings merge into a candidate pool, staples are added, and ChatGPT picks from the pool until the deck reaches 99 cards.
  - Result: power fell between the EDHRec popularity decks (best) and random decks. LLM re-ranking beat the embedding-only pools.
  - Failure mode: the LLM favoured generic "staples" over synergistic cards, which raised power but lowered synergy. Synergy-only decks could lack ramp and interaction.
  - The authors conclude that historical play data was the best signal for building a high-power deck.
  - [EDH-LLM](https://evelynyee.github.io/edh-llm)
- **ChatGPT-generated Yu-Gi-Oh! decks on YGOPRODeck (c. 2023):**
  - The page warns that ChatGPT often produces a deck under 40 cards, or puts Extra Deck cards in the Main Deck.
  - Another post notes the model's knowledge ended in Sept 2021.
  - [YGOPRODeck ChatGPT deck](https://ygoprodeck.com/deck/chatgpt-c-deck-323766)
- **Famitsu test (May 2025), ChatGPT-built Yu-Gi-Oh! deck for an offline event:**
  - ChatGPT described a card's effect incorrectly, and the first list needed repeated corrections.
  - When tested in Master Duel, the deck had too few starters and a combo that was too slow, so the author hand-patched it.
  - The author concluded that hallucinations are common with obscure cards, so the user needs card knowledge.
  - [Famitsu 2025-05](https://www.famitsu.com/article/202505/41577)
- **Konami Master Duel "auto deck building" (Nov 2024), a non-LLM production reference:**
  - The user adds one or more seed cards, and the AI fills the rest of the Main and Extra Deck.
  - It draws on deck data created by players worldwide, and Famitsu judged the output strong enough to compete.
  - [Famitsu 2024-11](https://www.famitsu.com/article/202411/23591)
- **Practitioner (Nov 2025), MTG deck review with Claude:**
  - Given card names only, the AI "confidently make[s] up mana costs, invent[s] abilities" and miscounts cards.
  - The author built a tool that pulls real card data from Scryfall and precomputes counts. They report it made the AI "a lot more useful", but did no formal testing.
  - [xopla.net](https://xopla.net/posts/a-little-tool-to-make-ai-better-at-magic-the-gathering-deckbuilding)
- **Anecdotal deck-building failures:**
  - A Pauper Jumpstart attempt: the model struggled to produce valid decks, reused cards, and got the deck size wrong. [DEV Community](https://dev.to/peter_vanonselen_e86eab6/the-zero-to-vibe-coding-jumpstart-cube-catastrophication-5ce3)
  - ChatGPT built a Commander deck with little synergy with its commander. [Wargamer](https://www.wargamer.com/magic-the-gathering/ai-commander-deck); [MTGGoldfish](https://www.mtggoldfish.com/articles/chatgpt-builds-our-decks-commander-clash-s15e2)
- **Pokémon TCG card generation (Pfau & Vrettis, arXiv 2604.27972, Apr 2026):**
  - Generates single cards, not decks. Qwen3-14B fills the card data as JSON, guided by RAG over about 993 real cards embedded with nomic-embed-text-v1.5.
  - The JSON schema "eliminated empty fields and syntax errors" in their tests.
  - Remaining failures: hallucinated mechanics that don't exist, repetition, and imbalanced cards.
  - [arXiv 2604.27972](https://arxiv.org/html/2604.27972)
- **Non-LLM drafting (DraftFM, arXiv 2608.19568, Aug 2026):**
  - A 1.6M-parameter model that represents each card only by its features and a text embedding, so it can score unseen cards.
  - Top-1 agreement on fully held-out sets was 50.8–60.4%.
  - The abstract reports no LLM comparison.
  - [arXiv 2608.19568](https://arxiv.org/abs/2608.19568)
- **Hearthstone:**
  - The closest LLM work found pairs a fine-tuned T5 with RL for gameplay generalization, not deck construction (AAMAS 2025). [AAMAS 2025](https://aamas.csc.liv.ac.uk/Proceedings/aamas2025/pdfs/p2795.pdf)
  - A community MCP server, "hearthstone-oracle", gives LLMs card data and deck-code decoding. [GitHub](https://github.com/gregario/hearthstone-oracle)

### Inferences
- The recurring failure modes, in rough order of frequency:
  1. Hallucinated or misremembered card effects, worst for obscure or older cards.
  2. Illegal structure, such as a wrong deck size or Extra Deck cards in the Main Deck.
  3. Weak synergy, or a default to generic staples.
  4. Misread timing and rule interactions, especially negative synergies.
- Tag Force uses a 2006–2011-era card pool, Chinese/Japanese text and game-specific limits, which makes failures 1 and 2 more likely. Every card fact should therefore come from the database, and structure must be checked in code.
- The strongest signals in this evidence are co-occurrence data from real decks (EDH-LLM, Master Duel). With only a handful of recipes, co-occurrence statistics will be thin. The LLM's general archetype knowledge plus card-text retrieval must cover the rest, with the recipes used as style and ratio guides.

### Gaps
- No published head-to-head of 2026 frontier models (Claude Opus/Sonnet 5.5, GPT-5.x, Gemini 3) on full constructed deck building with hallucination or legality rates.
- Per-model numbers for the Slay the Spire synergy paper: the PDF text could not be extracted.
- No Yu-Gi-Oh!-specific academic study was found. Whether the ygo-ai-bench GitHub project uses an LLM could not be checked (403 on fetch).

## 2. Grounding patterns: retrieval, tool use, structured output, generate–validate–repair

### Takeaway
Use three layers, from least to most reliable:
1. Retrieval or tool calls supply real card text.
2. Structured output (strict JSON schema or strict tool use) makes the output parse.
3. A deterministic validator in code checks legality, and its errors go back to the model for repair.

Constrained decoding guarantees valid JSON, not game legality. Claude's schema subset cannot express deck-size or count limits, so a validator is still required.

### Cited Findings
- **Claude structured outputs (current docs, late 2026):**
  - Constrained decoding guarantees responses match a JSON schema. It is enabled with `output_config.format` of type `json_schema`, or with `strict: true` on a tool. Both are stable with no beta header, on Opus/Sonnet/Haiku 4.5 and later, including `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`.
  - Supported: `enum`, `const`, `anyOf`, internal `$ref`, and `minItems`/`maxItems` only for values 0 or 1. Not supported: numeric `minimum`/`maximum`, other `minItems`/`maxItems` values, string-length limits, and recursive schemas.
  - Complexity limits per request: 20 strict tools, 24 optional parameters and 16 union-type parameters. Overly large grammars fail with "Schema is too complex for compilation". The docs give no maximum enum size.
  - Compiled grammars are cached for 24 hours. Changing `output_config.format` invalidates the prompt cache.
  - [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- **Card-DB tool servers for MTG:** Several community MCP servers wrap the Scryfall API (card search, details, deck building), and some write decks back to Archidekt. This shows a common practitioner pattern: give the LLM a card-search tool instead of relying on its memory. [mtg-mcp on PyPI](https://pypi.org/project/mtg-mcp); [Scryfall MCP](https://images.glama.ai/mcp/servers/bmurdock/scryfall-mcp); [command-tower-mcp](https://lobehub.com/mcp/nathanfdunn-command-tower-mcp); [kapunga deckbuilder-mcp](https://lobehub.com/mcp/kapunga-deckbuilder-mcp)
- **Enriching the decklist before the LLM sees it:** Pre-fetching real card text and computing counts in code reduced invented abilities and miscounts. [xopla.net, Nov 2025](https://xopla.net/posts/a-little-tool-to-make-ai-better-at-magic-the-gathering-deckbuilding)
- **Embedding retrieval over card text:**
  - EDH-LLM combines text-embedding similarity with feature-vector similarity to build the candidate pool the LLM picks from. [EDH-LLM](https://evelynyee.github.io/edh-llm)
  - The Pokémon generator retrieves its nearest real cards as few-shot examples. [arXiv 2604.27972](https://arxiv.org/html/2604.27972)
- **Generate–validate–repair in the wider research:**
  - FALCON combines grammar-constrained decoding, a semantic repair layer and preference training to reach 100% feasibility on LLM-generated combinatorial solutions. Its authors note that other methods treat feasibility as a soft objective. [arXiv 2602.01090](https://arxiv.org/html/2602.01090v1)
  - CP-Agent: the LLM writes constraints and a CP solver computes the answer, with an iterative refinement loop. With direct prompting, Python CP frameworks reach up to 65% accuracy on CP-Bench. [arXiv 2508.07468](https://arxiv.org/html/2508.07468v3)
  - A constraint-model agent that checks and repairs its reformulations in a ReAct loop improved on the original model in 68.5% of cases. [arXiv 2608.08127](https://arxiv.org/pdf/2608.08127)
  - Feeding error messages and prior outputs back to the LLM for correction is a standard repair step. [arXiv 2501.15081](https://arxiv.org/pdf/2501.15081v1)
- **Too much text can hurt:** In UrzaGPT, adding full card text lowered GPT-4o's zero-shot pick accuracy from 43% to 38%. [UrzaGPT](https://arxiv.org/html/2508.08382v1)

### Inferences
- **Recommended architecture for a fixed, closed card pool (a few thousand cards, never changing):**
  - (a) Preprocess each card once into a compact record: ID, name in Chinese, Japanese and English where available, type, attribute, level, ATK/DEF, and effect text. Add LLM-generated tags such as "searcher", "special-summon enabler", "negate", "archetype: X" or "starter/extender". Store these offline.
  - (b) Expose tools: `search_cards(filters, text_query)` and `get_cards(ids)`, plus `validate_deck(deck)`, which returns precise errors such as "3 copies of limited card #1234", "main deck 38 < 40", or "Fusion monster in main deck".
  - (c) Have the final answer be a strict JSON list of `{card_id, count}`. Card IDs are integers or strings checked against the DB in code. A 3,000+ entry enum is probably too large for grammar compilation, so check IDs after the fact instead of in the schema.
  - (d) Loop: validator errors go back to the model for repair, capped at 2–3 rounds. Then a deterministic fixer handles anything left, for example trimming to the deck size or swapping illegal copies for the highest-ranked legal candidates.
- **Keep the LLM's context lean:** let the LLM pick from a pre-filtered candidate pool of perhaps 100–300 compact card records. Don't dump the whole database or full card text at once. The UrzaGPT drop with full text supports this.
- **Use code for anything countable**, such as deck size, ban/limit list, Main/Extra split and copy limits. The LLM decides what to include and in what ratios; code checks whether the result is legal.

### Gaps
- No published measurement of how much hallucination rates fall with tool-grounded versus memory-only deck building for a TCG. The evidence is anecdotal.
- No documented maximum enum size for Claude strict schemas. A test is needed before relying on an enum of card IDs.

## 3. Using a few recipes as few-shot examples or retrieval context; deck completion from seeds; LLM plus classical search

### Takeaway
"Seed cards in, completed deck out" is a proven production pattern (Konami's Master Duel), but it runs on large player-deck data. With only a few recipes, a practical design uses the recipes in two ways: as retrieved few-shot templates for ratios and roles, and as weak co-occurrence priors. The LLM then proposes cards and a solver or validator makes the deck legal and fills it.

### Cited Findings
- **Master Duel auto deck building (Nov 2024):** the user supplies any number of seed cards, and the system fills the Main and Extra Deck from global player deck data. [Famitsu](https://www.famitsu.com/article/202411/23591)
- **EDH-LLM's hybrid pipeline:** a classical similarity ranking builds the candidate pool, staples are added, and the LLM iteratively selects until the deck is full. It beat embedding-only pools, but historical deck data was still the best predictor of power. [EDH-LLM](https://evelynyee.github.io/edh-llm)
- **Retrieved nearest examples as few-shot context:** the Pokémon generator retrieves its closest real cards as examples, combined with a JSON schema. [arXiv 2604.27972](https://arxiv.org/html/2604.27972)
- **LLMs over-pick generic staples:** in EDH-LLM, the LLM's selections leaned toward generic staples at the cost of synergy. [EDH-LLM](https://evelynyee.github.io/edh-llm)
- **Missing "engine" roles:** the hand-patched Famitsu deck lacked enough starters, a role-ratio problem. [Famitsu 2025-05](https://www.famitsu.com/article/202505/41577)

### Inferences
- **Suggested pipeline for Tag Force:**
  1. The user picks a seed card or theme.
  2. Retrieve the 1–3 most similar recipes, by shared card IDs or tag overlap, and include them verbatim as examples, annotated with roles and counts.
  3. Build a candidate pool by archetype name match, effect text that mentions the seed's name, type or attribute, tag overlap, and staples from the recipes.
  4. The LLM outputs a role plan (e.g. 12–15 starters/extenders, N hand traps or backrow, Extra Deck targets), then a card list with a one-line reason per card.
  5. The validator or solver enforces the rules and fills or trims by a score that mixes recipe co-occurrence and LLM rank.
  6. Optionally, the LLM writes a critique of the final list.
- **Asking for explicit role counts** (starters, extenders, removal, defence) is a cheap counter to the "too few starters" and "staples over synergy" failures seen above.
- **An alternative classical half:** a small knapsack or ILP over (card, count) with constraints (40–60 Main, 0–15 Extra, copy and ban limits, role minimums) and an objective of LLM scores plus recipe co-occurrence. This makes legality exact and lets the LLM focus on scoring. OR-Tools or PuLP can run it locally in milliseconds at this scale (an inference, not benchmarked here).
- **Measurement:** with only a few recipes, a reasonable offline check is deck completion. Remove 30–50% of a known recipe and measure how many removed cards the system restores (recall@k), plus how often its output is legal.

### Gaps
- No published few-shot deck-recipe study measures how many example decks are needed, or whether retrieved versus fixed examples help.
- No Yu-Gi-Oh!-specific evidence on LLM role-ratio planning.

## 4. Non-English (Chinese/Japanese) card text and cards the LLM may not know

### Takeaway
No source directly measures LLM accuracy on Chinese or Japanese Yu-Gi-Oh! card text. The evidence shows hallucination is worst for obscure cards and that grounding fixes much of it, so the safe design never relies on the model's memory of a card: every card the model reasons about must arrive with its database text.

### Cited Findings
- **Obscure cards:** the Famitsu author (Japanese-language play) observed that hallucinations are common with obscure cards, and ChatGPT misdescribed a card's effect. [Famitsu 2025-05](https://www.famitsu.com/article/202505/41577)
- **Knowledge cutoff:** ChatGPT's training cutoff left it unaware of newer cards (2023 YGOPRODeck note). [YGOPRODeck](https://ygoprodeck.com/deck/chatgpt-c-deck-323766)
- **Card text from names alone:** given only card names, Claude "doesn't actually know what [the cards] do" in a practitioner's MTG test. Supplying real card text fixed it. [xopla.net](https://xopla.net/posts/a-little-tool-to-make-ai-better-at-magic-the-gathering-deckbuilding)
- **Anthropic's multilingual claim:** all current Claude models support multilingual input, and the docs list multilingual tasks among their strengths. [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- **Token cost of Chinese/Japanese text:** the current tokenizer (since Opus 4.7) fits about 2.5M Unicode characters in 1M tokens. CJK text usually tokenizes less efficiently per character than English, but I found no Anthropic figure specific to CJK. [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)

### Inferences
- **Keep card identity separate from card name:** have the model output DB IDs, not names, and give each card record in context its ID. Chinese, Japanese and English names can then differ, and matching in code is exact rather than fuzzy.
- **Pre-tag cards offline:** run every card's Chinese/Japanese effect text through the LLM once in a batch job, using the Batch API at a 50% discount. Extract structured tags (role, archetype references, summon conditions, searcher targets) into the DB. The live deck builder then reasons over tags plus short text. This converts misreadings from a live risk into an offline data-quality issue that can be spot-checked.
- **Translation:** the card text is static, so a one-time English gloss or official English text can sit beside the Chinese/Japanese text. A translation layer at runtime is unnecessary.
- **Tag Force-specific cards:** treat any game-exclusive or unfamiliar card as "unknown to the model". Make its DB text the only source, and say in the system prompt that unseen cards are normal and must be judged from the text given.

### Gaps
- No benchmark of LLM accuracy on Japanese or Chinese Yu-Gi-Oh! effect text, such as parsing PSCT-style timing or "once per turn" clauses.
- No CJK-specific token-per-character figure from Anthropic docs.

## 5. Cost, latency, and current Claude API features (late 2026)

### Takeaway
For a personal tool, a single deck build costs cents with current Claude models, especially with prompt caching. The fixed card-DB slice and the recipes form a stable prefix that caches well, which makes API use cheap enough that a local model is mainly worth it for offline or privacy reasons. Small local 7–8B models were unreliable zero-shot at card selection unless fine-tuned (2025 evidence).

### Cited Findings
- **Current models (Anthropic docs, retrieved 2026-11-02):** all have 1M-token context, 128K max output, adaptive thinking and a June 2026 reliable knowledge cutoff. [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)

  | Model | API ID | Price (input / output per MTok) | Notes |
  |---|---|---|---|
  | Claude Fable 5.1 | `claude-fable-5-1` | $10 / $50 | Demanding reasoning |
  | Claude Opus 5.5 | `claude-opus-5-5` | $4 / $20 | Recommended default |
  | Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | Fast |
  | Claude Haiku 5.5 | `claude-haiku-5-5` | From $0.10 / from $0.50 | Fastest |

- **Batch discount:** Batch API requests are 50% off. [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- **Prompt caching:**
  - Pricing relative to base input: 5-minute cache writes cost 1.25×, 1-hour writes cost 2×, and reads cost 0.1× (0.05× on Opus 5.5 and Sonnet 5.5, 0.025× on Fable 5.1).
  - Minimum cacheable prompt is 512 tokens on Opus 5.5, Sonnet 5.5 and Haiku 5.5. Requests can have up to 4 breakpoints.
  - Changing tool definitions invalidates the whole cache. Changing thinking or effort settings invalidates the cached messages.
  - [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- **Structured outputs and strict tool use:** both are stable and add a small system prompt. The first use of a schema adds compile latency, and compiled grammars stay cached for 24 hours. [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- **Local open models (Aug 2025):** zero-shot 7–8B models often failed instructions and picked cards that were not offered. LoRA fine-tuning on about 1M examples brought them to roughly 64–66% pick accuracy, which requires a large dataset. [UrzaGPT](https://arxiv.org/html/2508.08382v1)
- **Local small-model JSON (Apr 2026):** a local 14B model (Qwen3-14B) with RAG and a JSON schema worked well enough for single-card generation in a user study. [arXiv 2604.27972](https://arxiv.org/html/2604.27972)

### Inferences
- **Rough per-build cost (my arithmetic from the listed prices):**
  - Assume a prompt of about 30K tokens (system rules, 2–3 recipes, about 200 candidate card records) plus 2–3 tool or repair turns, and about 3K output tokens per turn.
  - On Sonnet 5.5, that is about $0.06 for the first uncached input, about $0.003 per cached re-read, and about $0.03 output per turn. In total, roughly $0.10–0.20 per deck.
  - On Opus 5.5 it is about 2× that. Haiku 5.5 is much cheaper and could suit tagging or pre-filtering.
  - These are estimates, not measurements.
- **Caching layout:** put the stable parts (rules, ban list, recipe examples, tool definitions) first with a cache breakpoint. Put the per-request seed and candidate pool after it. Keep tools and effort settings fixed between calls so the cache stays valid.
- **Model split:**
  - Offline: use a cheap model (Haiku 5.5, Batch API) to tag the whole card DB once.
  - Live: use Sonnet 5.5 or Opus 5.5 for deck planning and repair.
  - Use code for validation and the solver.
- **Latency:** expect seconds to tens of seconds per build with 2–3 tool round trips. That is acceptable for an editor where the user waits for one deck. The device itself (a TrimUI handheld) would only receive the finished deck file, with the LLM running on a PC or via the API.
- **Local-only option:** a local 7–14B model is feasible only if the LLM's role is narrow, such as re-ranking a pre-filtered pool with schema-constrained output and strong validation. 2025 evidence shows zero-shot small models are unreliable at open card selection.

### Gaps
- No published latency or cost benchmarks specific to LLM deck building.
- Current GPT-5.x and Gemini pricing and structured-output limits were not checked in this pass, so only the Anthropic side is current.
- The cost figures above are back-of-envelope inferences, not measured.
