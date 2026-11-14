# Algorithmic and ML Approaches to Automatic Deck Building in CCGs (emphasis: Yu-Gi-Oh!)

Research date: 2026-11-02. About 18 search/fetch calls. Several primary PDFs were only seen as abstracts or search snippets; this is flagged per item.

## Yu-Gi-Oh!-specific work (WindBot, ygo-agent, RL projects, embeddings, community generators)

### Takeaway
No published, working Yu-Gi-Oh! deck *builder* exists in the open-source or academic record I could find. The strongest YGO tooling is about *playing* (WindBot's hand-written per-deck executors; ygo-agent's RL agents on ygopro-core). Deck building is a roadmap item in ygo-agent and unfinished in the hobby YugiohAi repo. Card embeddings from deck co-occurrence exist (fferegrino), and a 2026 fine-tuned LLM produces legal decklists only about a third of the time.

### Cited Findings
- **ygo-agent (sbl1996).** Two parts: `ygoenv`, a gym-style environment built on envpool + ygopro-core, and `ygoai`, the RL agents. Training moved to JAX in April 2024 and gained LSTM support. Card text can be turned into LLM embeddings (`embed.pkl`, optional). — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent)
- ygo-agent decks are `.ydk` files (`--deck` takes one file or a directory). Only cards in `scripts/code_list.txt` are supported, and the "well-tested" decks are in `assets/deck`. **"Implement AI deck building" is still an unfinished roadmap item.** — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent)
- ygo-agent compute. A GTX 1650 laptop trains at about 1,000 steps/s, and a 50-iteration single-deck run takes about 3.5 min, reaching a 0.98 win rate against random play. The strong model used "over 100M games", which the author equates to 32 RTX 4090s for 5 days. Many-deck training "typically" needs 8x4090 plus a 128-core CPU for a few days. There is no measured comparison against WindBot or humans. The last news item is from July 2024 (human-vs-AI play in the Neos client). — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent). Some third-party directories describe it as DQN-based; the README points to PPO / cleanba scripts. — [search summary of README vs creati.ai listings](https://www.github.com/sbl1996/ygo-agent)
- **WindBot.** A C# deterministic bot for YGOPro / EDOPro that joins a room as a virtual player. Each deck must be "specifically prepared and compiled as individual executors" (per-deck C# logic with hooks such as `OnSelectPosition` and `OnSelectAttackTarget`). A community Java tool generates executor templates from a deck. WindBot can also run as an HTTP server that creates bots on request. — [IceYGO/windbot](https://github.com/IceYGO/windbot); [knight00 fork](https://github.com/knight00/windbot)
- **YugiohAi (crispy-chiken).** A hobby project that pairs a Python "deck-building AI" (`deck_gen/`, `generate_deck.py`) with a WindBot-based game AI. The game AI learns action weights from logged games through an HTTP weight server; an MCTS option is marked "(Old)". The README says the end goal is to "find the best deck as well as play optimally" but gives no quantitative results. It has a `WinRate by CardId.csv` and config knobs such as `TotalGames` and `WinThreshold`. — [GitHub YugiohAi](https://github.com/crispy-chiken/YugiohAi)
- **Card embeddings from deck co-occurrence (fferegrino).** The `yu-gi-oh-card-vectors` / `card-embeddings` repos build YGO card embeddings from a co-occurrence matrix of cards that appear together in player decks, and power a card recommender. A related PyData London 2024 talk covers the same topic. — [search listing: fferegrino/yu-gi-oh-card-vectors](https://awesome.ecosyste.ms/projects/github.com%2Ffferegrino%2Fyu-gi-oh-card-vectors); [PyData London 2024](https://london2024.pydata.org/cfp/talk/VXWJUJ/feedback). The repo page itself returned HTTP 403, so the data source and deck count are unverified.
- **LLM deck generator (2026).** `qwen3-4b-ygo-meta-v3` is a Qwen3-4B fine-tuned with LoRA (MLX) on about 2,235 examples (837 top-cut tournament decklists plus 150 refusal negatives) for the 2026-05-18 TCG format. On a 58-scenario test, the best version (v8) scored 0.393 spec adherence and **0.372 legality**. v6 scored 0.25 / 0.21 but passed refusals 0.87 of the time. Published 2026-08-20. — [featherless.ai model card](https://featherless.ai/models/johnjmartin97/qwen3-4b-ygo-meta-v3)
- No arXiv paper specifically on Yu-Gi-Oh! deckbuilding turned up. The closest results are generic CCG papers (Q-DeckRec) and MTG papers. — [search results incl. Q-DeckRec](https://arxiv.org/pdf/1806.09771)
- A `maskdotdev/ygo-ai-bench` repo appeared in search listings, but I did not inspect it. — [listing](https://awesome.ecosyste.ms/projects/github.com%2Fmaskdotdev%2Fygo-ai-bench)

### Inferences
- For a Tag Force (TF6/TFSP) editor, ygo-agent is far too costly to reuse as a deck evaluator: GPU training per deck, a modern-card list (`code_list.txt`), and no deck-building module. WindBot needs hand-written executor code per deck, so it cannot score arbitrary generated decks fairly. A generic or default executor would play badly.
- The free-form LLM result (37% legal at best) argues for *constraining* any generator by construction: a 40-60 card main deck, at most 3 copies, the banlist, and the owned/unlocked pool. In practice the model only ranks or picks cards and never emits a full list unchecked.
- Co-occurrence embeddings (fferegrino-style) are the YGO method closest to "works from a modest recipe set". They are cheap to build (a matrix factorization or word2vec over decks) and fit a card recommender for deck completion.

### Gaps
- Could not read fferegrino's repo (403), so its data source, deck count and evaluation are unknown.
- Did not verify which `.ydk` AI decks WindBot ships or how many card IDs it supports. Did not inspect `ygo-ai-bench`.
- No source found on how well ygopro-core / WindBot handle Tag Force-era card sets. Tag Force card IDs would also need mapping to YGOPro passcodes; this is not researched here.

## Other CCGs: Hearthstone, MTG, Legends of Code and Magic, Pokémon TCG

### Takeaway
Hearthstone has the most rigorous deckbuilding-by-search work: GA (2016), MAP-Elites with Sliding Boundaries (2019), "Evolving the Hearthstone Meta" (2019) and DSA-ME (2022). All of it relies on a fast simulator (SabberStone) and hundreds of CPU-hours. MTG work centres on imitating human picks (draft bots) and on deck completion from large deck corpora (collaborative filtering, embeddings, transformers). LOCM provides compact RL/GA "arena draft" results. Pokémon TCG has only commercial or pre-launch efforts.

### Cited Findings
**Hearthstone**
- 2016 IEEE CIG: a genetic algorithm for deck building whose fitness comes from a game simulator testing each candidate against "a varied and representative range of human-made decks". — [iris.polito.it record](https://iris.polito.it/handle/11583/2666239) (abstract only)
- Fontaine et al., GECCO 2019, "Mapping Hearthstone Deck Spaces through MAP-Elites with Sliding Boundaries". It frames deckbuilding as a quality-diversity problem and introduces MESB to handle unevenly distributed good solutions; applied to deck generation and rebalancing. — [arXiv 1904.10656](https://arxiv.org/pdf/1904.10656)
- de Mesentier Silva, Fontaine, Canaan, Lee, Togelius, Hoover (2019), "Evolving the Hearthstone Meta". Its focus is *balance*: it uses MAP-Elites-generated decks over the Basic/Classic sets to measure how card changes shift strategy, with an evolutionary search for minimal card changes. — [arXiv 1907.01623](https://arxiv.org/pdf/1907.01623) (details from abstract/snippets, not full text)
- Zhang, Fontaine, Hoover, Nikolaidis, GECCO 2022, **Deep Surrogate Assisted MAP-Elites (DSA-ME)**: — [arXiv 2112.03534](https://ar5iv.labs.arxiv.org/html/2112.03534)
  - Representation: "bag of cards" integer vector (0-2 copies per card); Rogue class, 180 candidate cards, 30-card decks.
  - Evaluation: SabberStone simulator, **200 games per deck** spread over 6 opponent decks; 10,000 ground-truth evaluations per run.
  - Cost: 5 trials per algorithm on a 200-Xeon-CPU cluster, **10-12 h per trial**.
  - Results (max win %): MAP-Elites 90.6, Offline DSA-ME 97.1, Linear-surrogate 96.2, DSA-ME 98.4; QD-score 136.9 -> 338.5. Win-rate differences among the surrogate methods were not statistically significant.
  - Mechanism: an online MLP surrogate predicts deck performance; an inner MAP-Elites loop searches on the surrogate, and the outer loop verifies elites in the simulator.
- **Q-DeckRec** (Chen et al., CIG 2018): learns a deck-search policy offline with RL, then solves new deckbuilding instances (pool + fixed size + target opponents) with less computation than baselines. It notes that a single GA run "took hours or days" because every fitness evaluation needs many simulated matches. — [arXiv 1806.09771](https://arxiv.org/abs/1806.09771); [CIG PDF](https://web.cs.ucla.edu/~yzsun/papers/2018_cig_deckrec.pdf)

**Magic: The Gathering**
- Ward et al. 2020, "AI solutions for drafting in MTG". Uses a Draftsim.com pick dataset to compare four agent types; a neural network was best at imitating human picks, and Naive Bayes and expert-tuned agents beat simple heuristics. It did **not** evaluate deck strength in simulated play; deck building from finished drafts is listed as future work. The authors estimate about 10^700 starting conditions and about 10^40 trajectories for one 250-card set. — [arXiv 2009.00655](https://arxiv.org/pdf/2009.00655); [Draftsim write-up](https://draftsim.com/?p=64732)
- Bertram, Fürnkranz, Müller 2024, "Learning With Generalised Card Representations for MTG". Embeds the current deck and candidate cards, then picks the candidate closest in embedding space. Features drawn from card text and attributes let it generalize to unseen cards, predicting about 55% of human picks on completely unseen cards. The choice of representation matters little for known cards but a lot for new ones. — [arXiv 2407.05879](https://arxiv.org/pdf/2407.05879)
- DeNichilo (Ramapo MSDS, 2025): a Commander deck recommender using collaborative filtering via ALS matrix factorization over **more than 200,000** player-built decks. — [thesis PDF](https://www.ramapo.edu/dmc/wp-content/uploads/sites/361/2025/06/2025-02-MSDS-DeNichilo.pdf)
- magicBERT (Hugging Face community model): a masked-LM-style transformer for Commander **deck completion**. It conditions on a partial deck, fills the remaining slots, and uses Hungarian matching for permutation invariance. Its claims are unverified. — [HF magicBERT](https://huggingface.co/nishtahir/magicBERT)
- An IEEE DataPort MTG drafting dataset describes a Siamese network that learns a preference embedding by comparing cards in deck context. — [IEEE DataPort](https://ieee-dataport.org/documents/magic-gathering-drafting-data)

**Legends of Code and Magic (LOCM)**
- Vieira, Tavares, Chaimowicz 2020 (SBGames), "Drafting in CCGs via RL". Its deep-RL draft agents beat the best existing draft agents while building very different decks. Pairing a competition player with the best draft agent moved it from 10th to 4th place in the Strategy Card Game AI competition. — [SBGames PDF](https://www.sbgames.org/proceedings2020/ComputacaoFull/209690.pdf); [SBC](https://sol.sbc.org.br/index.php/sbgames_estendido/article/view/19743)
- Yang, Yeh, Chiang 2021 (IEEE SSCI): a GA tunes the parameters of card-scoring functions for deck building; scoring by card attributes was effective. — [GP bib entry](https://gpbib.cs.ucl.ac.uk/gp-html/Yang_2021_SSCI.html); [Chiang publications](https://web.ntnu.edu.tw/~tcchiang/publications/ssci2021a.htm)
- Kowalski & Miernik 2020, "Evolutionary Approach to CCG Arena Deckbuilding" (LOCM). — [arXiv 2001.01326](https://arxiv.org/abs/2001.01326) (title only; content not read)
- ByteRL (2024) is a state-of-the-art LOCM agent, and a later analysis found it highly exploitable. — [arXiv 2404.16689](https://arxiv.org/pdf/2404.16689v1.pdf) (snippet only)

**Pokémon TCG**
- DeNA presented an RL battle AI for Pokémon TCG Pocket at CEDEC 2026. It is used for CPU opponents and automated battles with a player's deck, and its deck-building step treats each basic Pokémon as a candidate while accounting for synergy. Rule-based AI struggled with the combinatorics. — [Inven Global](https://www.invenglobal.com/articles/24133/how-reinforcement-learning-ai-tackles-the-complex-rules-of-pok%C3%A9mon-trading-card-game-pocket)
- tcgslayer (Pokémon TCG AI deck builder plus simulator) is pre-launch. — [tcgslayer](https://tcgslayer.pages.dev/)
- No academic GA/RL deckbuilding paper for the paper Pokémon TCG was found. — same search

### Inferences
- The Hearthstone pipeline needs a fast, faithful simulator, a competent generic play policy and about 10^6 games. It works because SabberStone plus simple greedy/heuristic agents are "good enough" for Hearthstone. Yu-Gi-Oh! combo decks depend much more on the play policy, so simulation fitness would mostly measure the bot rather than the deck.
- LOCM's attribute-based card scoring tuned by GA is the closest analogue to a cheap, interpretable heuristic builder that could run on a handheld.

### Gaps
- Did not read full texts of the 2016 Hearthstone GA paper, "Evolving the Hearthstone Meta", Q-DeckRec (game used, exact numbers) or Kowalski & Miernik 2020.
- Did not find 17lands-based draft-bot papers or the MTG "deck2vec" notebooks; no Kaggle notebooks were checked.

## Small recipe sets vs. large datasets; what "deck completion" is and how it is evaluated

### Takeaway
Methods that learn from human decks (collaborative filtering, co-occurrence embeddings, transformers, LLM fine-tunes) were all reported on hundreds to hundreds of thousands of decks. The smallest data point found is the YGO LLM at 837 tournament lists, and it still produced mostly illegal output. With a few dozen to a few hundred recipes, the realistic options are co-occurrence statistics or association rules plus hand-written structural constraints, or content-based features (card attributes and text), which also generalize to unseen cards. Deck completion means filling the missing slots of a partial deck; it is usually evaluated by hiding cards from real decks and measuring recovery, or by human-pick prediction accuracy.

### Cited Findings
- Data scale per method: 200,000+ Commander decks for ALS CF ([DeNichilo](https://www.ramapo.edu/dmc/wp-content/uploads/sites/361/2025/06/2025-02-MSDS-DeNichilo.pdf)); 837 top-cut YGO lists, about 2,235 examples, for an LLM reaching 0.37 legality ([featherless](https://featherless.ai/models/johnjmartin97/qwen3-4b-ygo-meta-v3)); Draftsim pick logs for draft bots ([arXiv 2009.00655](https://arxiv.org/pdf/2009.00655)); 10,000 random decks to pretrain the offline DSA-ME surrogate ([arXiv 2112.03534](https://ar5iv.labs.arxiv.org/html/2112.03534)).
- Content-based card features (text and attributes) greatly improve predictions on unseen cards (about 55% human-pick accuracy) even though they barely matter for seen cards. — [arXiv 2407.05879](https://arxiv.org/pdf/2407.05879)
- Deck completion as a task: magicBERT conditions on a partial Commander deck and fills the remaining slots. — [HF magicBERT](https://huggingface.co/nishtahir/magicBERT). The pick-imitation metric (top-1 agreement with human picks) is the standard in draft-bot papers. — [arXiv 2009.00655](https://arxiv.org/pdf/2009.00655); [arXiv 2407.05879](https://arxiv.org/pdf/2407.05879)
- Purely search-based methods need **no example decks**, only a simulator and opponent decks (DSA-ME, Q-DeckRec, LOCM GA). — [arXiv 2112.03534](https://ar5iv.labs.arxiv.org/html/2112.03534); [arXiv 1806.09771](https://arxiv.org/abs/1806.09771)
- Data-source terms: the YGOPRODeck API documents only card endpoints (`cardinfo.php`, `cardsets.php`, `archetypes.php` and others) and no deck endpoint. It is limited to 20 requests/s, exceeding that brings a 1-hour block, and users must download and re-host images rather than hotlink. — [YGOPRODeck API guide](https://ygoprodeck.com/api-guide/). Per the task brief, the site owner declined deck APIs, so no deck scraping. ygo-agent ships its own `.ydk` decks in `assets/deck`. — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent)

### Inferences
- For Tag Force, where the user has at most a few hundred recipes (e.g. in-game CPU decks or structure decks), a sensible stack is:
  1. Card-pair co-occurrence or PMI (or association rules) computed from those recipes, which is easy to do with very little data.
  2. Content features from the card DB: type, attribute, level, archetype or name-string matches, and effect keywords, as a fallback for cards never seen in recipes.
  3. Greedy or beam completion from a seed (archetype or key cards), filling slots under hard constraints such as ratios and copy limits.
- The likely evaluation is leave-k-out recovery on the recipe set: hide 5-10 cards and measure recall@k for the hidden ones. This is a guess based on common recommender practice and is not confirmed by a cited YGO paper.

### Gaps
- No source found giving actual leave-k-out metrics for CCG deck completion. magicBERT and the DeNichilo thesis were seen only as summaries, so their metrics are unknown.
- No source tested how few decks co-occurrence methods need; this is unverified.

## Simulation-based evaluation: can ygopro-core / WindBot score a deck, and at what cost?

### Takeaway
Technically yes: ygopro-core runs headless and ygo-agent wraps it as a high-throughput gym environment. But reliable deck scoring needs (a) a play policy that is competent for *arbitrary* decks, which WindBot lacks (per-deck executors) and ygo-agent provides only after very costly training, and (b) many games per deck: Hearthstone work used 200 games per deck across 10,000 decks, about 10-12 h on 200 CPUs. For a personal Tag Force editor, simulation is at best an optional offline sanity check, not the core method.

### Cited Findings
- ygoenv is described as "high performance" (envpool + ygopro-core). A laptop GPU reaches about 1,000 training steps/s. — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent)
- A strong general policy needed about 100M games (about 32x4090 for 5 days); there is no comparison to WindBot. — [GitHub ygo-agent](https://github.com/sbl1996/ygo-agent)
- WindBot needs a deck-specific compiled executor, and a changelog notes a bug where a second `AI.SelectCard` activation in one chain selects wrongly. — [search summary of WindBot repos](https://github.com/IceYGO/windbot)
- Hearthstone simulation cost reference: 200 games/deck, 10,000 evaluations, 10-12 h on 200 Xeon CPUs. — [arXiv 2112.03534](https://ar5iv.labs.arxiv.org/html/2112.03534). GA deck search "took hours or days" per instance. — [arXiv 1806.09771](https://arxiv.org/abs/1806.09771)
- A surrogate model (an MLP predicting deck win rate) cuts the number of simulator calls needed. — [arXiv 2112.03534](https://ar5iv.labs.arxiv.org/html/2112.03534)

### Inferences
- Win rates from WindBot's default or generic executor would reflect bot skill more than deck quality, which makes the scores unreliable. Simulation also cannot run on the Brick-class device itself; it would have to run offline on a PC.
- A cheaper proxy is "goldfish" consistency simulation: draw thousands of opening hands and check whether a starter or combo condition is met, with no opponent. It needs only card-role tags plus hypergeometric math or Monte Carlo sampling (see the next section).

### Gaps
- No measured games-per-second figure for headless ygopro-core with WindBot was found.
- No study found comparing WindBot win rates with human deck strength.

## Yu-Gi-Oh! structure heuristics and consistency math

### Takeaway
Community practice treats deck quality mainly as *consistency*: the probability of opening a starter, measured with the hypergeometric distribution over a 40-card deck and a 5-card hand (6 cards going second). Cards are tagged by role (starters, extenders, handtraps, bricks). For example, 13 starters in 40 cards gives about 87.7% to open at least one, versus about 63.9% with 7.

### Cited Findings
- Draws are without replacement, so the hypergeometric distribution is the correct model, and smaller decks see key cards more often. — [everycalculators](https://everycalculators.com/hypergeometric-calculator-yugioh.html)
- P(at least one of 3 copies in a 5-card hand, 40-card deck) is about 33.76%. — [codingace hand calculator](https://codingace.net/general/yugioh_hand.html) (graphcalc's 34.5% is slightly off: [graphcalc](https://www.graphcalc.com/?p=1139))
- 40-card deck with 13 starters gives about 87.7% to open at least one starter in 5 cards; 7 starters gives about 63.9%. — [Cardmarket Insight](https://cardmarket.com/en/Insight/Articles/The-Mathematics-Behind-Building-Competitive-Decks)
- YGOPRODeck explains how to adjust the calculation for going first (5 cards) versus second (6), with a worked example of about 39.4% for one copy when going second. — [YGOPRODeck hypergeometric article](https://ygoprodeck.com/yu-gi-oh-hypergeometric-probability-distribution-function)
- Role-tagged calculators (starters, extenders, bricks, traps) exist as community tools. — [codingace](https://codingace.net/general/yugioh_hand.html)
- A forum claim that 60-card decks can be more consistent for some combos is untested. — [Duelists Unite](https://forum.duelistsunite.org/t/ygo-probability-calculator/1753)

### Inferences
- A cheap, interpretable Tag Force builder could combine:
  - hard constraints: 40 cards (40-60 legal), at most 3 copies, the game's ban list, and the owned/unlocked pool;
  - a role-tagging pass (starter, extender, searcher, removal, handtrap/defensive trap, boss, brick), done manually or via keyword rules on card text;
  - an objective that maximizes P(open at least 1 starter) via hypergeometric math plus synergy, using co-occurrence/PMI from recipes and shared archetype or name strings;
  - greedy, beam or GA search in the LOCM style.
  It needs no GPU and no simulator, and can work from a few dozen recipes.
- Monster/spell/trap ratios for the Tag Force era (older formats are more trap-heavy and less combo-driven) were not sourced. They should come from the user's own recipe set, e.g. per-archetype averages from in-game CPU decks.

### Gaps
- No sourced numbers for typical monster/spell/trap ratios or for starter/extender/handtrap counts in modern versus GX/5D's-era (Tag Force) decks.
- No sourced study of Monte Carlo "combo-line" simulation for YGO beyond simple hypergeometric calculators.
