# Front-End Phase 3 (GATE-1) — In-App Candidate Discovery (build spec)

**Build contract for GATE-1 of the front-end milestone.** *Build status + what's next live ONLY in
`COLLABORATION_CONTEXT.md` § Status & roadmap (not here — avoids drift).*

Pairs with `FRONT_END_DIRECTION.md` (D5: GATE-1 = conversational, ledger-grounded discovery) and the North Star
(GATE 1 = *the user defines the market → the LLM proposes candidates → the user approves*).

---

## 1. What GATE-1 delivers

A conversational, ledger-grounded **candidate discovery** surface in the app: you describe/refine your target
market in a chat; an LLM (OpenAI + **web search**) proposes **real, currently-operating** health-tech companies,
grounded in your saved thesis + your full scored roster + your manual overrides (and never re-proposing anything
already researched); you refine by talking to it, then **approve** a candidate list. That approved list is the
durable GATE-1 output. **Bridge (for now):** the approved list feeds the **Colab** research/scoring run (as today)
— replacing Colab with a hosted runner is the LAST Phase-3 piece, not this one.

Rule 7 holds: the LLM **gathers/proposes** candidates (evidence); the **human approves** at GATE-1; the
deterministic §B **scoring happens later** (in research). GATE-1 never scores.

## 2. Locked decisions (2026-07-04, with Katelynd)

- **Conversational** chat, grounded in the ledger (D5).
- **Provider: OpenAI + web search** — consistent with the research pipeline; reuse `research_runner`'s
  client-injected `call_openai` pattern (the `responses` API + web-search tool). Web search is **mandatory** and
  **anti-hallucination**: verify each company exists / get its latest status, or drop it.
- **Saved thesis** — editable in-app, stored durably in the Drive data folder, pre-loaded each session, refinable
  in the chat.
- **Taste grounding = the manual priority overrides (with reasons)**, NOT the P0/P1 scores — the strongest signal
  of Katelynd's judgment. Lean toward companies resembling the ones she *raised*; the ones she *lowered* are a
  weaker fit.
- **Full scored roster injected** (compact — one line per company); the **raw research write-ups are NOT injected**
  (~40K chars/company × 54 ≈ 2M chars — too large and unnecessary; the scores/priority summarize them). Deep
  research on a specific company can be pulled on demand later.
- **6–10 candidates per round**; exclude everything already researched.

## 2a. The locked discovery prompt (highest-stakes — signed off 2026-07-04)

Placeholders in `{{…}}` are filled from the ledger at call time.

```
You are helping Katelynd find health-tech companies to research for her career search — she wants a ROLE at a
company that fits her, not an investment. Propose real, current companies to add to her research list.

Her target market (her saved thesis — the baseline; she may refine it in the chat):
{{thesis}}

Already researched — do NOT propose any of these again:
{{researched_company_names}}

Her manual priority overrides — where she personally disagreed with the model and set her own priority, in her
own words. This is the strongest signal of her taste:
{{overrides: "company (segment · model · stage): model said <tier>, she set <tier> — '<reason>'"}}
Lean toward companies that resemble the ones she raised; treat the ones she lowered as a weaker fit.

Her full scored roster (how everything she's researched ranks, and why — the numbers-led view):
{{roster: "company · segment · model · stage · <final priority> · Bg <n> / PMF <n> / Strain <n> / FINAL <n> · <key flag>"}}

Propose 6–10 candidates that:
- are real, currently-operating health-tech companies — USE WEB SEARCH to verify each exists and get its latest
  status (stage, recent funding). Never invent or guess; if you can't verify it, drop it.
- fit her thesis (plus anything she adds in the chat) and resemble her raised overrides where it makes sense.
- are NOT already in her researched list.

For each: company name · one line on why it fits (tie to her thesis or her overrides) · a quick search signal
(stage + latest funding, or what they do).

Then ask if she wants to refine (more like one, earlier-stage, different segment, drop some). Keep it a
conversation; approval is a separate step. Be honest about assumptions and about any company you're unsure fits
— don't pad the list.
```

## 2b. Grounding payload (built from the ledger each session)

- `thesis` — the saved thesis text.
- `researched_company_names` — every company in the ledger (the exclude list).
- `overrides` — entries with `decision.human_override` set → `company (segment · model · stage): model said
  <model_priority>, she set <final_priority> — '<override_reason>'`.
- `roster` — one compact line per company: `company · segment · model · stage · final priority · Bg/PMF/Strain/FINAL
  · key flag`. **No** raw findings / `fit_brief_json`.

## 3. Flow + surface (routes, gated by login)

- `GET /discover` — the discovery page: an **editable thesis box** (pre-loaded from Drive) + the **chat** + a
  running **"proposed candidates"** panel (selectable items you curate).
- `POST /discover/thesis` — save the edited thesis back to Drive (read-back verified).
- `POST /discover/message` — send a chat turn → the LLM (system prompt §2a + grounding §2b + conversation +
  web search) returns conversational text **plus a structured list of proposed candidates** (so the app can render
  them as add/keep/drop items).
- `POST /discover/approve` — write the approved candidate list to Drive (the durable GATE-1 artifact) → shown as
  the hand-off to research.

## 4. Persistence

> **Auth constraint (locked 2026-07-05, live-verify):** the Google **service account cannot CREATE files** in the
> free-Gmail My Drive folder — `files.create` always 403s (`storageQuotaExceeded`; Shared Drives / OAuth delegation
> need paid Workspace). It can only **UPDATE files Katelynd owns**. So both GATE-1 files are **pre-created by
> Katelynd** (uploaded once) and the app only updates them. See the `sa-cannot-create-drive-files` note.

- **Thesis:** `thesis.md` in the Drive data folder (Katelynd-owned; uploaded once, pre-filled with her approved
  thesis). The app **updates** it in place (read-back — Rule 4/5); a missing file RAISES an actionable error rather
  than attempting a (doomed) create.
- **Approved candidates:** a single **append-only `candidates.csv`** (Katelynd-owned; uploaded once with just the
  header). Columns `date,company,why,signal`; each approval **appends** its rows stamped with the date and updates the
  file in place, so prior batches are preserved and distinguished by `date`. This is the durable GATE-1 artifact the
  research run consumes (replaces the earlier `candidates_<date>.csv` per-file plan — dated files can't be created).
- **Conversation:** session-scoped working state (not a durable gate artifact); only the approved list is durable.

## 5. Config

- **OpenAI API key** as a Render env var (`OPENAI_API_KEY`) — same key family as the research pipeline. Local dev
  uses Katelynd's key. The `openai` dep is in the **`web` extra** (the deploy runs `pip install -e ".[web]"`), because
  GATE-1 makes the OpenAI call server-side — it is NOT enough to have it only in the `research` extra.
- Model: the same `responses` API + web-search tool the research pipeline uses (client-injected, so offline tests
  run with a fake client — no key needed).

## 6. Rules honored

- **Rule 7** — LLM proposes; human approves at GATE-1; deterministic §B scoring is downstream (research). GATE-1
  does not score or decide priority.
- **Prompt wording** designed + signed off with Katelynd (§2a) — the highest-stakes change.
- **Rules 4/5** — the thesis + approved-list writes are durable + read-back-verified.
- **Public repo** — the OpenAI key is a Render secret; no secrets/data committed.

## 7. Out of scope (later)

- The **server-side research/scoring runner** (replaces Colab) — the last Phase-3 piece; GATE-1 bridges to Colab.
- Auto-triggering research from an approved list; progress + notification (built with the runner).
- `candidate_priority.py` deterministic ranking of the proposals (optional later; discovery is LLM-proposed +
  human-approved).

## 8. Build order

1. **Grounding + prompt builders** from the ledger (`grounding_payload`, the §2a prompt) — offline unit tests.
2. **OpenAI discovery call** (client-injected, web search, structured candidate output) — offline tests with a
   fake client (the `research_runner` pattern).
3. **Thesis read/write** (Drive) + the `/discover` page (thesis editor + chat + candidate panel + approve).
4. **Approved-list write** to Drive.
5. Tests green; **live-verify** with Katelynd's OpenAI key on real data.
