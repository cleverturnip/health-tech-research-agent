# PRE-REGEN READINESS — the single GO artifact

**Built against FRAMEWORK_VERSION v1.2** (the scoring SOURCE OF TRUTH; the SOT doc + the classifier
fixture live on the `docs-scoring-sot` branch, read by both tracks). Research-recovery code is on
`research-search-recovery`. **This is the one page Katelynd green-lights the run-once regen against** —
not a reconstruction from the 14 findings sections in `audits/all_fields_probe_findings.md`.

**GO statement.** Every *required research input* has been validated before the irreversible, ~$-expensive
run-once. Each recovery field's N was **sized from measured data, never reflexively**; the one gate-critical
selector (funding) is a **deterministic mapper with a fail-safe flag**, not LLM free-reasoning. Nothing
below is an open question that should block the run; the open items in §4 are explicitly *non-blocking*.

---

## 1. Locked per-field treatment & N — every required research input

**Recovery fields** — *always-run-N passes, UNION the findings, presence check is observability-only*
(it changes only the `figure_present` provenance flag; it never alters the union or the pass count).
Mechanism: `search_with_recovery` (`56118e1`). N>1 was **earned by measured presence-fragility** — a single
pass can MISS a figure that exists → false absence → wrong gate/score — so each N is set for ~97%+ recall
from the field's own re-measure, not a round number.

| Field | Treatment | N | Wired (commit) | Validation basis |
|---|---|---|---|---|
| `revenue_or_arr` | source-directed recovery | **5** | config `20476e0`, wired `048777a` | Group-1 re-measure; Pelago (Quit Genius) falsified "genuine absence" → presence-fragile |
| `growth_rate` | source-directed recovery + precision fence | **5** | trio `3605144`, wired `745a2f0`, fence `5ffbe7e` | §10 growth re-measure |
| `paying_customer_count` | source-directed recovery | **5** | config `b1fdfbc`, wired `1e47e5d` | Group-1 re-measure |
| `funding` (rounds) | source-directed recovery | **2** | config+fail-safe `a434cec`, mapper `c3779cc`, robustness+N-lock *(this commit)* | §11→§14: 2c variance → mapper → recall → source-directed re-measure shows recall **~100%/pass** → N=2 is a thin buffer, not N=4 |

**Group 2** — no dedicated recovery pass:
- `valuation` — **single-pass, context-only.** Shared the funding search; measured to blink 0–100% but it is
  NOT a gate input, so its noise is tolerated as context (it never decides a gate/priority). (`52e11d5`)
- `revenue_per_user` — **derive-in-synthesis**, no new search (computed from gathered revenue + a scale
  denominator at synthesis time). (`52e11d5`)

**Diffuse single-pass set** — gathered once because each is a *captured evidence* field, NOT a measured
gate-flip-variance input the way revenue/funding are; their gate/score *consumption* is a post-regen
scoring-track step (so one faithful capture suffices). Where a field is captured-but-not-yet-scored it is
carried **blind-provisional** into the scoring track:
- `payer_finding` / institutional-distribution — single-pass capture. *(blind-provisional: the
  employer-direct PATH scope refinement is parked for the scoring track — §4.)*
- outcomes evidence — single-pass; clinical-outcomes facts, not a run-to-run gate-flip risk.
- `reset_events` — single-pass; recomputable from `reset_events_json`; multi-event handling already built.
- capability-fit evidence (A1/A2/A3) — single-pass *gather*; **scored** later in Slice 4 (blind-provisional).
- operational-strain — single-pass; observational signal, routed (B6.1) not directly scored.
- `user_scale_signal` — single-pass; **NEW** (B6.1 secondary-signal routing, `5ffbe7e`). Captured + carried;
  **NEVER satisfies revenue presence and NEVER feeds `growth_score`** (blind-provisional — routed to its
  B6.1 slot, scored in the scoring track).

**Funding SELECTION (Rule 7 — the LLM gathers, code decides).** The fit-brief synthesis emits structured
`maturity_evidence.funding_rounds` + `ipo_event`; the **deterministic mapper** `funding_stage_from_rounds`
picks the SOT-B4 stage (public/IPO outranks; else the latest-dated PRICED-EQUITY round; non-canonical types
— "Priced equity round" / "unknown" / secondary sales — are excluded from selection; `series-X extension`
folds to `series-X`). The mapper never lets a garbage type win over a real Series D (§14). Two review routes
guard the gate: (a) an **`unknown`/undeterminable stage from ANY cause ALWAYS routes to human review** —
checked before the recent-round short-circuit, so the robustness fix can never hide a silent gate pass/fail;
(b) **flag-don't-gate fail-safe** — an early stage with NO recent priced round AND an inconsistency (old
company OR scaled commercial signal) flags for review; never on ABSENT alone (a quiet-but-healthy company is
not flagged). `funding_rounds_json` is persisted (recomputable). 278 tests green, validated offline / zero
credits on the exact re-measure round-lists.

---

## 2. Classifier / Option B status (who_uses / who_pays)

- **who_uses / who_pays is a POST-regen recompute** (Option B): the regen persists trustworthy *evidence*;
  the classifier re-extracts the label later. It is NOT on the regen's critical path.
- **Evidence confirmed sufficient 55/55** — who_uses/who_pays facts are present in the commercial / payer /
  operating findings for every company; an evidence-only classification reproduced the locked fixture
  exactly. No regen-blocking gap.
- The **in-repo fixture** `specs/business_model_classifier_fixture.md` (on `docs-scoring-sot`; 7 B2B-floor +
  11 B2C + 37 B2B2C = 55, 9 canonical asserts) is the **regression target** for the classifier's live test.
- The **5 B2C↔B2B2C boundary cases are a prompt-dial, not evidence gaps** — they resolve in the classifier's
  prompt/threshold tuning during the scoring track, not by gathering more research.

---

## 3. Final cost — LOCKED

**~1,155 web searches** = 55 companies × **21 web calls/company**
[revenue 5 + growth 5 + paying 5 + commercial 5 + **funding 2**], **+ 55 fit-brief synthesis calls**
**+ per-field presence checks.** Funding 1→2 added +55 over the ~1,100 baseline.

This is **~2× the first regen.** The delta is deliberate — it is **the price of NOT baking untrustworthy
multi-field data into a run-once.** The first regen ran fields at N=1 and shipped false-absence /
gate-flip noise; this regen pays for measured recall on every presence-fragile and gate-critical input.

---

## 4. Known carried items that do NOT block the regen

(Listed so they are not lost — none is a regen blocker.)
- **`payer_institutional` employer-direct scope fix** — parked for **PATH Test B** in the scoring track.
- **Old-flow `search_funding` shadowing hazard** — logged on the cleanup tracker (`9178fc3`); the live path
  uses the package `search_funding`, so it does not affect the regen.
- **AGENCY late-C dial + the funding fail-safe thresholds** (`FUNDING_FAILSAFE_AGE_YEARS`,
  `FUNDING_FAILSAFE_COMMERCIAL`, the ~24-mo presence window) — **DIALS with conservative defaults**, tunable
  later; they only route to review, never gate.
- **`videahealth` deliberately absent** — JSON-retry hardening is scheduled; its omission is intentional,
  not a data miss.

---

## 5. What the regen produces, and what comes after

- **Produces:** a **trustworthy multi-field master** — revenue / growth / paying-count / funding captured at
  measured recall, funding stage deterministically mapped, secondary signals routed.
- **Then the scoring track resumes** (separate from this regen): classifier **live test vs the fixture**, the
  gate/gradient spine, the Background Fit rewording, and **calibration against the 55 on trustworthy data**.
- **BARRED:** calibration on pre-regen data. The whole point of the regen is to replace the untrustworthy
  inputs first; tuning the decision logic against the old noisy master is explicitly not allowed.

---

## 6. Pre-flight checklist for the actual run (the operational gate)

Run through this immediately before the GO — it is the operational gate, separate from the data-readiness
above:

- [ ] **Billing confirmed** — credits present + the monthly auto-recharge cap is high enough for ~1,155
  searches. (A sustained "Rate limit hit … Max retries reached" almost always means OUT OF CREDITS, not
  throttling — **CHECK BILLING FIRST**, per the runbook.)
- [ ] **Correct branch + version** — research code at `research-search-recovery`; FRAMEWORK_VERSION v1.2;
  the per-field N constants read 5 / 5 / 5 / 2.
- [ ] **DRY_RUN gate first** — run the dry-run path before the real write; confirm it reports the expected
  per-company call budget (21 web/company) and writes nothing durable.
- [ ] **Resume / idempotency intact** — a disconnect mid-run must resume from the last durable per-company
  checkpoint without re-researching completed companies (do NOT unlink the checkpoint on a post-restart
  resume).
- [ ] **Read-back verifies POPULATION, not just presence** — the first regen's blank-cluster miss came from
  checking that the workbook *exists* instead of that the cells are *populated*. The completion gate must
  re-open the artifact and confirm the fields are actually filled across the company set, not merely that a
  file was written.

---

*After this page is approved, nothing remains but Katelynd's run-once GO.*
