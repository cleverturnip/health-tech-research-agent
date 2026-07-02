# Slice 4 — Real Capability-Fit (three-attribute company-shape rubric)

Replaces the interim bridge (`capability_fit_score` currently returns the existing
`katelynd_role_fit_score`, framework "V4.2-interim") with a real, LLM-produced
capability-fit score. This is the field the candidate-priority gate consumes
(P0 requires capability >= 78, P1 >= 74), so it directly affects tiering.

## What capability-fit measures (reframed from the original write-up)

The original spec §3D framed this as "do Katelynd's capabilities apply" — a flat list of
skills. The redesign reframes it as a COMPANY-SHAPE fit: how closely does this company
match the shape of company where Katelynd is exceptional. This is more checkable against
company evidence than a skills-match guess, and it aligns with the framework's
"owns meaningful business outcomes" intent (a company of this shape is one where her kind
of leadership is central, not supporting).

The original §3D capability list is RETIRED. Mandate/breadth lives in the agency-entry
score, NOT here — so the two scores stay distinct and do not double-count.

## Scoring model
- Score = AVERAGE of three attributes, each 0-100, EQUAL THIRDS.
- The LLM assigns each attribute a 0-100 score WITHIN a band, with a one-line justification.
- Deterministic code averages the three (round, clamp 0-100).
- Bands (guides for the LLM's per-attribute score):
  - Strong   85-100  (clearly, centrally true of the company)
  - Moderate  60-84   (present, with caveats)
  - Weak      30-59   (mostly absent or only superficial)
  - Absent     0-29   (not characteristic at all)

## The three attributes

> **A1 and A2 are reframed by Slice 3.7** (`specs/slice3_7_search_layer_redesign_spec.md` is
> the source of truth for both definitions). A1 = product-engagement structure (data-driven by
> necessity); A2 = operational strain (NOT "complexity exists"). A3 unchanged. The equal-thirds
> scoring model above is unchanged — only the A1/A2 definitions change.

### A1 — Product-engagement structure → data-driven by necessity
**Reframed by `specs/slice3_7_search_layer_redesign_spec.md` (source of truth).** A1 is NOT a
"do they have a data culture" inquiry — that is unverifiable and companies self-describe. It is
a PRODUCT-STRUCTURE question: a product with a daily/habitual engagement loop whose REVENUE
DEPENDS on sustained engagement is data-driven BY NECESSITY — the economics force it,
regardless of whether they do it well.
- Score HIGH when the product is habit-dependent AND revenue hangs on retention.
- Score LOW when engagement is periodic/optional, or revenue doesn't depend on it (a
  one-time/transactional purchase, or analytics feeding slow planning cycles rather than the
  product's own daily loop).
- Asymmetry preserved: doing the data loop badly is the value-add, not a disqualifier — the
  structural dependence is what scores, not execution quality.
- Evidence (shared with A3): `search_operating_characteristics`, product-engagement lens.

### A2 — Operational STRAIN (not "complexity exists")
**Reframed by `specs/slice3_7_search_layer_redesign_spec.md` (source of truth).** A2 is NOT
"cross-domain complexity exists" — the LLM finds that for every competitive company, so it does
not discriminate. It is EVIDENCE OF OPERATIONAL STRAIN: scaling outrunning process, things
breaking under growth — the signal that the company needs someone with this operator's skillset.
- INTENDED BEHAVIOR: a healthy, smoothly-scaling, well-run company scores LOW on A2 — the strain
  IS the opportunity, so its absence correctly lowers fit.
- Consequence to expect in regenerated data: a "better" (coping) company can score LOWER on
  capability-fit than a struggling one. That is correct and intended.
- Evidence: `search_operating_characteristics`, operational-strain lens.

### A3 — Digital consumer habitual-engagement product
A DIGITAL CONSUMER product where HABIT / RETENTION is LOAD-BEARING for the product's
success.
- False positive (score low): a consumer SURFACE without habit-dependence (one-time
  transaction), or B2B2C where the real customer is the employer/payer and habit is
  secondary.
- Unchanged in intent; now explicitly SHARES the product-engagement evidence with reframed
  A1 (both fed by `search_operating_characteristics`).

## LLM output (persisted as columns)
- `capability_a1_score`, `capability_a1_basis`
- `capability_a2_score`, `capability_a2_basis`
- `capability_a3_score`, `capability_a3_basis`
- `katelynd_capability_fit_score` (the average — may be computed in code from the three)

Persisting the three components (not just the average) follows the same principle as
Slice 2: the score is a deterministic function of stored components, so the averaging /
weighting could be recalibrated later without re-research if ever needed. (Equal-thirds is
the decision now; storing components keeps it adjustable.)

## Integration with the engine
- After this lands, repoint the package's `capability_fit_score` (candidate_priority.py)
  from the role_fit bridge to the new `katelynd_capability_fit_score` field.
- Update `CANDIDATE_FRAMEWORK_VERSION` from "V4.2-interim" to the real version (e.g. "V4.2")
  once capability-fit is no longer a bridge — this is the signal that priorities are no
  longer interim.
- NOTE: this is also the point at which Commit 5 (candidate -> final authority) becomes
  unblocked, per the overall sequencing — capability-fit being real is the gate condition
  for trusting candidate priorities enough to drive final_priority_level.

## Build notes
- Add the three attributes (A1/A2/A3 with bands + justifications) to the fit-brief prompt
  (`run_company_fit_brief`) — the single insertion point feeding STEP 7 (fresh) and
  STEP 26 (rescore).
- Parse the three per-attribute scores + bases in the STEP 10 flatten; persist as columns.
- The averaging is a deterministic package function (testable): three numbers -> average,
  rounded, clamped; define the missing-attribute policy (if an attribute is unscorable,
  decide: flag + exclude, or treat as a documented default — recommend flag for review
  rather than silently averaging over a gap).
- Tests: averaging (three numbers -> rounded average); a clearly-on-shape company (all three
  strong) scores high; an off-shape company (e.g. B2B2C, periodic-data, bureaucratic-bigness)
  scores low; the bridge is fully replaced (capability_fit_score no longer returns role_fit).

## Calibration note (same as Slice 2)
Like the commercial signal, the per-attribute scores are somewhat relative ("strong data
culture for the space"). The first regeneration builds the reference frame; because the
components are persisted and the final score is a deterministic function of them, the
averaging/banding can be calibrated against the assembled distribution afterward without
re-research. First pass: gather the three attributes completely and granularly; calibrate
boundaries against the distribution later.
