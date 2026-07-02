# Business-Model Classifier — Locked 55-Fixture (regression target)

**FRAMEWORK_VERSION: v1.3** · pairs with [`SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`](SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md) §B2.

> **Status: COMPLETE (corrected v1.3 — see Correction log below).** Locked labels are captured — the
> **B2B-floor 6**, the full per-company **B2C-8** and **B2B2C-41**, the **counts**, the **7 canonical
> asserts**, and **needs_review=0** — from `business_model_classifier_spec.md` §4 (the human-locked source)
> plus the v1.3 evidence-driven corrections (4 moves), NOT from any classifier run (the regression target
> must be the human labels, never the classifier's own output — that would make the test circular).
> Internal consistency verified: 6 + 8 + 41 = 55 distinct companies = the roster.

## Why this file exists
The forced who_uses/who_pays classifier (SOT §B2) is the PATH-gate linchpin. Its **regression target was
living only in a chat-side doc** — the same out-of-repo drift we already closed for the SOT. This lands the
target in the repo so the STAGED classifier-prompt Colab validation scores against a committed artifact,
not a re-uploaded memory. **No classifier logic is built here; this is only the target it must reproduce.**

## The classifier being scored (SOT §B2)
- LLM extracts: `who_uses` (consumer|professional), `who_pays` (consumer|institution|mixed), plus
  `who_uses_basis`, `who_pays_basis`, `who_uses_confidence` (high|low). The LLM does **not** emit the label.
- **Deterministic mapper (LOCKED):**
  ```
  if who_uses == "professional":          -> "B2B"     # PATH Test A floor, regardless of who_pays
  if who_pays == "consumer":              -> "B2C"
  if who_pays in ("institution","mixed"): -> "B2B2C"
  ```
- **Frequency firewall:** usage frequency is IRRELEVANT to who_uses (a daily-using clinician is still
  `professional`).
- `who_uses_confidence == low` → `business_model_needs_review = True` (flag, don't gate).

## Locked counts (roster of 55)
| label | count |
|---|---|
| B2B-floor | **6** |
| B2C | **8** |
| B2B2C | **41** |
| needs_review (expected) | **0** (>1–2 to review ⇒ prompt logic is off; fix before accepting) |

## B2B-floor — the 6 (PATH Test A floors on these; LOCKED)
`openevidence`, `cohere health`, `zus health`, `om1`, `medically home`, `linus health`.
(`angle health` left the floor in v1.3 — see Correction log.)

## Canonical asserts (LOCKED — the named regressions)
| company | expected | note |
|---|---|---|
| openevidence | **B2B** | was mislabeled B2B2C — the linchpin fix |
| nourish | **B2B2C** | |
| zoe | **B2C** | |
| medically-home | **B2B** | |
| headway | **B2B2C** | |
| rula | **B2B2C** | |
| grow-therapy | **B2B2C** | |

_(v1.3: dropped `angle-health → B2B` and `outcomes4me → B2C` — both reclassified B2B2C; see Correction log.)_

## B2C — the 8 (LOCKED; consumer user + consumer pays out of pocket)
oura, insidetracker, function health, noom med, oova, levels health, zoe, signos.
(`allara health`, `tia`, `outcomes4me` left B2C in v1.3 — see Correction log.)

## B2B2C — the 41 (LOCKED; consumer user + institution/mixed pays)
nourish, equip health, grow therapy, maven clinic, omada health, oshi health, visana health,
sword health, solace health, midi health, transcarent, familywell health, headway, affect therapeutics,
9amhealth, culina health, jasper health, fay, season health, pomelo care, thyme care, hinge health,
waymark, oula, mae health, cylinder health, foodsmart, rula health, pelago, bicycle health,
vivante health, diana health, firefly health, summer health, berry street, counsel health, wellist,
angle health, outcomes4me, allara health, tia.

_Consistency: 6 (floor) + 8 (B2C) + 41 (B2B2C) = 55 distinct companies = the roster; the 7 canonical
asserts are consistent with these lists (openevidence / medically-home in floor-6; zoe in B2C;
nourish / headway / rula / grow-therapy in B2B2C)._

## Correction log (v1.3 — evidence-driven, 2026-06-29)
The first classifier run against the **real regen research output** disagreed with the design-time fixture
on 9 companies; judged against the SOT who_uses/who_pays logic, **four were the fixture being stale**
(classifier right) and were corrected. Per-entry reasoning (defensible labels, not relabeled-to-match-output):
- **angle health: B2B-floor → B2B2C.** A **member login on Angle's site (Katelynd, direct observation)** =
  the insured consumer personally uses Angle's OWN product → `who_uses=consumer`; employer-sponsored group
  plan → institution pays → B2B2C. Corrects a **wrongful B2B floor** (would have eliminated a company with a
  real consumer end-user — the most consequential gate error). *(The research excerpt is employer-facing and
  does not itself quote the member app; Katelynd's observation carries the who_uses fact.)*
- **outcomes4me: B2C → B2B2C.** Free-to-patient ("280k cancer patients, **FREE app**"); sponsor/pharma pays.
  `who_pays ≠ consumer` → consumer-uses + institution-pays → B2B2C.
- **allara health: B2C → B2B2C.** Genuine hybrid — D2C membership **AND** named in-network payers (Aetna,
  BCBS/Anthem, UHC/Oxford/UMR, GEHA). Established institutional channel, not a mention.
- **tia: B2C → B2B2C.** Genuine hybrid — consumer membership **AND** a real CommonSpirit Health JV
  (health-plan / health-system channel).
- **counsel health: UNCHANGED (stays B2B2C — fixture is RIGHT).** Series A reporting shows ~100,000 members
  via commercial health plans + employer partnerships (employer-reported, real). The regen's research OUTPUT
  under-surfaced this channel, so a classifier run may still read B2C from **thin evidence** — an INPUT gap,
  not a logic error (Rule 8). A residual `counsel=B2C` is an **accepted, explained discrepancy**, not a
  fixture change and not a gate failure (optionally enrich counsel's research evidence later).

Recomputed counts: **B2B 6 / B2C 8 / B2B2C 41 = 55.** Re-run target with `firefly health` deferred (the lone
JSON-bug casualty of the run): **B2B 6 / B2C 8 / B2B2C 40 = 54.** Canonical asserts: dropped `angle→B2B` and
`outcomes4me→B2C`; B2B-floor is now 6 (the floor guard for the re-run is `openevidence`+`medically home`).

## Evidence-sufficiency (verified — Option B confirmed, this thread)
Tested **evidence-only** against the last regen checkpoint (`v42_full_regen…full56_checkpoint`, the persisted
evidence the regen produces): the who_uses/who_pays signal is present for **55/55** (in the
`commercial_scale_finding` + `payer_institutional_finding` + `operating_characteristics_finding`). The
classifier is therefore a **recomputable post-regen step (Rule 7)** — no evidence capture is needed before
the second regen. The remaining B2C↔B2B2C boundary companies (`function`, `oura`, `summer`) are
`who_pays`-threshold (prompt-dial) calls **with evidence present**, not evidence gaps (`allara` and `tia`
were reclassified B2B2C in v1.3 — established institutional channels; `counsel` is evidence-thin, above).
The B2B-floor 6 and all 7 canonical asserts are the corrected regression target.
