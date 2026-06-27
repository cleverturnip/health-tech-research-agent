# Business-Model Classifier — Locked 55-Fixture (regression target)

**FRAMEWORK_VERSION: v1.2** · pairs with [`SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md`](SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md) §B2.

> **Status: COMPLETE.** All locked labels are captured — the **B2B-floor 7**, the full per-company
> **B2C-11** and **B2B2C-37**, the **counts**, the **8 canonical asserts**, and **needs_review=0** — from
> `business_model_classifier_spec.md` §4 (the human-locked source), NOT from any classifier run (the
> regression target must be the human labels, never the classifier's own output — that would make the
> test circular). Internal consistency verified: 7 + 11 + 37 = 55 distinct companies = the roster.

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
| B2B-floor | **7** |
| B2C | **11** |
| B2B2C | **37** |
| needs_review (expected) | **0** (>1–2 to review ⇒ prompt logic is off; fix before accepting) |

## B2B-floor — the 7 (PATH Test A floors on these; LOCKED)
`openevidence`, `cohere health`, `zus health`, `om1`, `medically home`, `linus health`, `angle health`.

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
| angle-health | **B2B** | |
| outcomes4me | **B2C** | |

## B2C — the 11 (LOCKED; consumer user + consumer pays)
oura, insidetracker, allara health, function health, noom med, oova, levels health, zoe, signos,
tia, outcomes4me.

## B2B2C — the 37 (LOCKED; consumer user + institution/mixed pays)
nourish, equip health, grow therapy, maven clinic, omada health, oshi health, visana health,
sword health, solace health, midi health, transcarent, familywell health, headway, affect therapeutics,
9amhealth, culina health, jasper health, fay, season health, pomelo care, thyme care, hinge health,
waymark, oula, mae health, cylinder health, foodsmart, rula health, pelago, bicycle health,
vivante health, diana health, firefly health, summer health, berry street, counsel health, wellist.

_Consistency: 7 (floor) + 11 (B2C) + 37 (B2B2C) = 55 distinct companies = the roster; the 8 canonical
asserts are consistent with these lists (openevidence / medically-home / angle in floor-7; zoe /
outcomes4me in B2C; nourish / headway / rula / grow-therapy in B2B2C)._

## Evidence-sufficiency (verified — Option B confirmed, this thread)
Tested **evidence-only** against the last regen checkpoint (`v42_full_regen…full56_checkpoint`, the persisted
evidence the regen produces): the who_uses/who_pays signal is present for **55/55** (in the
`commercial_scale_finding` + `payer_institutional_finding` + `operating_characteristics_finding`). The
classifier is therefore a **recomputable post-regen step (Rule 7)** — no evidence capture is needed before
the second regen. The ~5 B2C↔B2B2C boundary companies (`function`, `oura`, `allara`, `tia`, `summer`) are
`who_pays`-threshold (prompt-dial) calls **with evidence present**, not evidence gaps. The B2B-floor 7 and
all 8 canonical asserts reproduced from the evidence.
