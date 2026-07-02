# Classifier (§B2) — staged-prompt validation flags + shelved edits

> **Non-normative carry note.** Pairs with `SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md` §B2 (FRAMEWORK_VERSION
> **v1.13**) + `business_model_classifier_fixture.md` (v1.3). Records the carried basis flags and the one
> shelved prompt edit from the gate-B classifier-prompt validation, so nothing critical lives only in chat.
> The §B2 EVIDENCE-ONLY who_pays rule itself is normative and lives in the SOT (v1.13).

## Status — gate-B prompt validation COMPLETE (2026-06-30)

The staged who_uses/who_pays classifier prompt was validated against the 7 who_pays-boundary cases
(`signos`, `function health`, `oura`, `summer health`, `allara health`, `tia`, `outcomes4me`) over the
exact `v42_full_regen…full56_checkpoint_FINAL` evidence bytes (fingerprint-gated run). Result: **7/7 on the
correct label and who_pays side.** The prompt is **SIGNED OFF**, built against **SOT v1.13 / fixture v1.3**.
The EVIDENCE-ONLY clause was confirmed working in the model's own words (e.g. `oura` → `consumer`/B2C with
basis "does not materially establish an institutional payment channel **in the provided evidence**").

The mapper + fixture v1.3 are UNCHANGED. Both flags below are **basis-provenance imperfections, not label
errors** — every label is correct and the fixture regression target (counts + the 7 canonical asserts) is
unaffected.

## Carried basis flags (Rule-8 class — correct label, thin/imperfect provenance)

1. **`outcomes4me` — basis reads `who_pays=mixed` where the evidence supports `institution`.**
   - **What:** the model returned `mixed` (asserting a consumer-pay path) while the evidence states
     "primarily a **direct-to-patient, free app**" and "'supported' and 'members' are **not the same as
     paid customers**." It is a **free** app — there is no consumer-pay path; the pharma sponsors pay.
   - **Why it's inert (traced, not assumed):** the mapper maps **both** `institution` **and** `mixed` (with
     a consumer user) → **B2B2C**, so the label is correct either way. PATH gate runs on the label; PMF /
     bg_fit / strain / floor / thresholds run off the label + scored components; persisted `who_pays` is
     Rule-7 evidence (carried, never re-scored). No label, gate, score, or fixture result depends on the
     `mixed`-vs-`institution` distinction. Cause: a FREE-TO-CONSUMER **use-vs-pay conflation** in the prompt
     (the model read "direct-to-consumer *use*" as a consumer-*payment* path).
   - **Disposition:** ACCEPTED + carried. The fix is shelved below (apply when the prompt is next edited).
   - **Live-54 update (2026-06-30):** on the full-roster run `outcomes4me` read `who_pays=institution`
     (vs `mixed` in the 7-case slice) — **same prompt, same evidence bytes.** That is LLM run-to-run
     variance, and both reads map to **B2B2C**, which **confirms this flag is genuinely cosmetic**
     (non-deterministic + label-immaterial). The shelved clause would pin it to `institution`; still
     fold-at-next-edit, not a dedicated run.

2. **`allara health` — basis reads `who_pays=mixed` on evidenced "in-network in some states"; the named
   payers the fixture justification cited are NOT in this evidence slice.**
   - **What:** correct label (**B2B2C**) on a real evidenced institutional channel ("in-network insurance
     coverage in some states"). But the fixture v1.3 Correction-log justification cited specific named payers
     (Aetna / BCBS / Anthem / UHC / GEHA) that are **not present in this regen evidence slice** — the label
     lands on a thinner channel than the fixture prose assumed.
   - **Disposition:** ACCEPTED + carried as an **evidence-enrichment candidate** (Rule 8, same class as
     `counsel` evidence-thin) — correct label, thin provenance; optionally enrich allara's research evidence
     later. Not a blocker, not a fixture change.

## Shelved prompt edit (apply when the classifier prompt is NEXT touched — hardening)

**Do NOT spend a dedicated Colab run on this now.** It fixes the `outcomes4me` use-vs-pay conflation at
**zero marginal Colab cost** when the prompt is next edited anyway. This is a "apply at next edit" choice,
NOT "ignore forever" — parked here so the choice stays honest.

Replace the current `FREE-TO-CONSUMER` line in the Axis-2 MATERIALITY-BAR block with this sharper,
use-vs-pay-explicit version:

```text
- FREE-TO-CONSUMER (consumer USE is NOT consumer PAYMENT): a product the individual gets for FREE has NO consumer-pay path, no matter how directly the consumer uses it. Do NOT treat "direct-to-consumer" / "consumer-facing" USE as a consumer-PAYMENT path. If the consumer pays nothing and an institution (pharma / sponsor / employer / payer) materially pays, answer "institution" (NOT "mixed"). "mixed" requires the consumer to actually PAY money AND a real institutional payer.
```

Expected effect when applied: `outcomes4me` → `who_pays=institution` (label stays B2B2C); the other six
stable. No label change anywhere on the 54 (mapper-immaterial), so it does **not** require a fresh
calibration or a dedicated validation run — fold it into the next prompt-touch and re-confirm in that run.

## Live-54 fixture regression — Commit 1, 2026-06-30 (the durable record)

The committed classifier (`phase3-commit1-classifier`) was run over the full 54-company roster (firefly +
videahealth deferred), prompt → deterministic mapper/floor/overrides. **Clean PASS, reviewed by bucket
membership (not just totals):**

- **Counts: B2B 6 / B2C 8 / B2B2C 40 = 54** — exact fixture-v1.3 match. The **7 canonical asserts** all
  pass; **`needs_review` = 0**.
- **Bucket membership confirmed** — every company in the correct bucket (the check that catches
  compensating errors: right totals, wrong companies inside). The v1.3 hard cases land right:
  `angle`→B2B2C (wrongful-B2B-floor avoided), `allara`/`tia`/`outcomes4me`→B2B2C.
- **The human layers did real corrective work on LIVE reads** — classifier-alone scored **51/54**; the
  floor + overrides corrected the 3 it missed:
  - **`medically home` — the floor fired on a live raw-`B2B2C` MISS.** The classifier read it
    `consumer/institution` → raw label B2B2C (wrong); the floor forced **B2B**. This is the exact
    oscillation the floor was human-locked for — the adversarial local test predicted this *specific*
    company. The floor earned its keep, not hypothetically.
  - **`noom med` + `counsel health` overrides — both LOAD-BEARING.** noom raw `consumer/mixed` → B2B2C
    (the minor-channel who_pays over-read persists) corrected to **B2C**; counsel raw `consumer/consumer`
    → B2C (evidence-thin) corrected to **B2B2C**, with the raw read still surfaced (tolerated). The prompt
    fixes neither.
  - **`signos` override — RETIRED.** Live raw read `consumer/consumer` → B2C **equals** the override's
    value, so the override was **INERT** on live evidence. A redundant override would MASK a future prompt
    regression on signos, so it was removed (commit on `phase3-commit1-classifier`); signos now rides the
    mapper, where its correctness is visible + testable (same principle as the adversarial floor test).
    `DOCUMENTED_BUSINESS_MODEL_OVERRIDES` now holds only `noom med` + `counsel health`.
- Local deterministic suite: **35/35** (incl. the adversarial floor); full suite **313** — no regression.

**Net:** the classifier (prompt → deterministic layer) reproduces fixture v1.3 end-to-end; the two
remaining overrides + the floor are proven load-bearing on live reads, not carried on faith.
