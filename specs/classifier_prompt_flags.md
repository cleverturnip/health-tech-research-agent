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
