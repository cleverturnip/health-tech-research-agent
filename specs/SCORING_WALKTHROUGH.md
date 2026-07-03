# How the scoring works — a plain walkthrough

**What this is:** a plain, end-to-end walk of how ONE company travels from raw research to a priority tier
on the GATE-2 card. It's the "follow the company through the machine" narrative — legible without any chat
history.

**How it relates to the other docs (don't duplicate them):**
- `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` (the SOT) = **the rules** (the exact thresholds, gates, scales;
  FRAMEWORK-VERSION-stamped). If a number here and the SOT ever disagree, the SOT wins.
- `archive/specs/PHASE3_PROCESS_HISTORY.md` = **the why** (why each rule is shaped the way it is).
- **This doc = the walkthrough** (how a company moves through the steps, in order).
- `MASTER_REDESIGN_SPEC.md` §4 = where the result is **rendered** (the ledger + the review card).

---

## The one-paragraph shape

The model is **gated-then-ranked**. First, a few **reliable facts eliminate** companies that don't fit
(the *gates* — is there a consumer? is it early enough to still shape?). A gated company is capped at the
bottom tier (P3) no matter how it scores. Everything that survives the gates is then **ranked** by a few
1–10 judgment scores (the *gradients*), which add up to a FINAL score that maps to a tier. **A floor caps
PRIORITY, not scoring** — every company is fully scored; a floor just prevents it from rising above P3.

The order a company travels: **classifier → PATH gate → AGENCY gate → Background Fit → Product Market Fit
(ARR + Growth) → Strain → FINAL → floor rule → tier threshold → human override → flags.**

---

## Step by step

### 1. Classifier — B2B / B2C / B2B2C  (`§B2`)
The LLM reads the evidence and answers two narrow questions: **who *uses* the product** (a consumer, or a
professional like a clinician?) and **who *pays*** (the consumer, or an institution?). A deterministic
mapper turns those into the label — the LLM never picks the label itself.
- `who_uses = professional` → **B2B** (a behind-the-scenes tool; no consumer to build for).
- `who_pays = consumer` → **B2C**;  `who_pays = institution/mixed` → **B2B2C** (a consumer end-user, an
  institution helps pay).
- A short **human-locked list** of 6 known-hard B2B companies is forced to B2B regardless of the read
  (the classifier can't reliably hold that boundary).

### 2. PATH-to-scale gate — is there a consumer, and is the engine alive?  (`§B3`)
- **Test A:** if the label is **B2B**, the company is **floored** here — there's no consumer end-user to
  build for. (This is the `b2b_floor`.)
- **Test B:** for B2C / B2B2C, a loose "is it alive?" check — some revenue, user scale, or growth signal.
  Only the genuinely dead are floored. Engine *strength* is NOT judged here (that's Product Market Fit's job).

### 3. AGENCY gate — is it early enough to still shape the build?  (`§B4`)
Read purely from **funding stage** (a reliable fact). Series A / B / early-C **pass**; Series D+ / public
**fail** (too late to join and still shape it) — *unless* a **reset** fired (a new CEO, a real
restructuring) that reopens the build window. A fail here is the `agency_floor`. Stage is score-critical,
so it's derived deterministically from the dated funding rounds (see the stage-resolution flow) — never guessed.

### 4. Background Fit — 1–10 gradient  (`§B5`)
How well does the company match a **consumer habit / data-feedback loop** (a daily-tracking product scores
high; a twice-a-year lab product scores low)? This is a *gradient*, not a gate — a misread lowers the score
a little, it never eliminates. It's a **consumer measure**, so a B2B company gets **n/a** (no consumer to
score). The read is taken 4× and averaged (it's the one genuinely noisy read).

### 5. Product Market Fit — 1–10, from ARR + Growth  (`§B6`)
Revenue judged **relative to stage** (a strong Series B beats a big-but-flat public co). Two halves:
- **ARR-level** (Scale A) — the revenue figure scored against a per-stage benchmark.
- **Growth** (Scale B) — the growth *band* (high / solid / slow / unknown) against per-stage cutoffs. A
  **fence** blocks non-revenue counts (covered-lives, members) from posing as revenue growth (`data_gap`).
- Composite = **40% ARR + 60% Growth** (growth-weighted — the thesis bets on the slope).

### 6. Strain — a small modifier, 0 to +2  (`§B7`)
A small bump for a company scaling hard (strong capability + fast headcount/volume growth). Capped at +2 so
it can never move a company across a tier on its own.

### 7. FINAL, the floor rule, and the tier  (`§B7`)
- **FINAL = Background Fit + Product Market Fit + Strain.**
- **Floor rule:** to reach P0/P1/P2 a company needs **BOTH** Background Fit > 4 **AND** Product Market Fit > 4.
  Fail that and it's **P3** regardless of FINAL (`low_score_floor`) — the deliberate "habitual vs episodic"
  split. (For a B2B company, Background Fit is n/a, so FINAL is n/a and it's floored anyway.)
- **Tier threshold** (floor-PASS companies only): **P0 ≥ 18 · P1 15–17 · P2 13–14 · P3 < 13.**

### 8. Human override — Rule 6  (at the gate, by Katelynd)
A documented "the model gets this one wrong" case (e.g. **Function Health**) is surfaced as an
**`override_candidate`** — it still shows its model tier, and Katelynd sets the real tier at GATE 2. Her
priority override always wins; scores are never hand-edited (Rule 8).

### 9. Flags — what fired  (`§3.5`)
Each triggered rule leaves a flag so it's visible at review: `b2b_floor`, `agency_floor`, `low_score_floor`,
`data_gap` (growth fence), `stage_low_confidence`, `override_candidate`, `tier_review` (FINAL sits on a tier
boundary).

**Precedence — each company is handled by exactly one layer:** a gate floor OR a low-score floor → **P3**;
otherwise the tier threshold; a human override is terminal on top of all of it.

---

## Worked examples

- **zoe (clean P0):** B2C, Series B, daily food logging (Background Fit 8), elite revenue + growth (PMF 9),
  Strain +2 → **FINAL 19 → P0**, nothing flagged → `accept`.
- **Function Health (floored-but-strong):** B2C, Series B, but only twice-a-year lab draws → Background Fit
  4. That **fails the floor rule** (needs > 4), so the model says **P3** despite a huge, fast-growing
  business. It's a documented `override_candidate` → carded, `review_override`, and you decide whether to
  lift it to P1.
- **medically home (B2B floor):** professional/enablement — no consumer end-user → **PATH Test A floors it**.
  Background Fit + FINAL are **n/a** (a consumer measure doesn't apply); ARR / Growth / Strain still compute.
  `b2b_floor`, `accept` (confirm the floor).
- **oura (agency floor):** B2C, but Series D+ → **AGENCY floors it to P3**. It's still fully scored (FINAL
  20 — a strong company), so you can *see* it's strong and choose to override if you disagree with the floor.

---

## Where it lands (the ledger + card)

Each company becomes one write-once entry in `ledger.jsonl`: the scores + rationale, the gate results, the
`model_priority` (the pure §B call), and an empty `decision` block. The GATE-2 **card** renders all of it —
scores, per-component *why*, the joined research evidence, the floors block, and the recommendation — and
you make one kind of decision: **keep the priority or override it** (see `MASTER_REDESIGN_SPEC.md` §4). The
`final_priority` you see = your override if you set one, else the model's tier.
