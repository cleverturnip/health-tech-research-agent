"""Research runner: the LLM research + fit-brief generation, migrated faithfully
out of ``colab_workflow.py`` (notebook STEP 3 / STEP 4 / STEP 5) into the package.

This is a *mechanical* migration. The prompts, model, JSON schema, parsing, and
scoring are unchanged from the notebook; the only structural changes are:

* The OpenAI ``client`` and ``model`` are dependency-injected (passed in) rather
  than constructed at import — so the package imports and tests run offline,
  with no API key, against a fake client. Colab still constructs the real client
  (from Colab Secrets) and passes it in, matching the taxonomy-block precedent.
* ``time.sleep`` is injected as ``sleep_fn`` so retry timing can be asserted in
  tests without actually sleeping. The default is the real ``time.sleep``.
* Retry/error diagnostics use ``logging`` instead of ``print`` (the package's
  existing convention; see ``models.py``). This is diagnostic output only — no
  change to control flow or return values.

The fit-brief prompt is split into a pure builder (``build_fit_brief_prompt``)
and the call (``run_company_fit_brief``): the builder returns the byte-identical
prompt string and is the prompt-fidelity test seam and the insertion point for
the later structured-evidence / reset / capability-fit slices (Slices 2-4).

``call_openai``'s retry semantics are preserved exactly: only ``RateLimitError``
retries (waiting ``90 * attempt`` seconds); ``APIError`` re-raises immediately.
(Narrowing the retry to transient API errors is a deliberately deferred,
separately-reviewable change — not part of this faithful extraction.)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import structured_evidence as se

try:  # openai is an optional extra (see pyproject); keep the package importable offline.
    from openai import APIError, RateLimitError
except ImportError:  # pragma: no cover - exercised only where openai is absent
    class RateLimitError(Exception):
        """Fallback used when the openai SDK is not installed."""

    class APIError(Exception):
        """Fallback used when the openai SDK is not installed."""

from .review import REQUIRED_RESEARCH_COLUMNS, parse_first_json_object
from .storage import atomic_write_csv, copy_with_backup, load_csv

logger = logging.getLogger(__name__)

# Faithful defaults copied from notebook STEP 2.
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_RETRIES = 3
DEFAULT_WAIT_BETWEEN_SEARCHES = 120  # seconds
# Inter-pass wait for search_with_recovery's N passes. NON-ZERO by design: the
# mechanism exploits web-search execution variance, so rapid-fire identical queries
# risk correlated / cached result sets that defeat the variance we depend on. Well
# short of the 120s between DISTINCT searches (these are retries of ONE query). This
# is a hypothesis to validate via the live run's pass-level logging — tune up if the
# passes come back near-identical.
DEFAULT_WAIT_BETWEEN_PASSES = 45  # seconds


SEARCH_FAILED_MARKER = (
    "[SEARCH_FAILED: empty model output after retry — evidence UNAVAILABLE, not absent]"
)


def is_search_failure(value) -> bool:
    """True if a finding is the empty-output failure marker — a FAILED search (evidence
    UNAVAILABLE), NOT a real finding and NOT 'no evidence'. Lets downstream treat a holed
    finding as a failure (re-research / flag) instead of as apparent absence."""
    return str(value).strip().startswith("[SEARCH_FAILED")


def call_openai(
    prompt,
    *,
    client,
    model: str = DEFAULT_MODEL,
    use_web_search: bool = False,
    max_output_tokens: int = 500,
    max_retries: int = DEFAULT_MAX_RETRIES,
    sleep_fn=time.sleep,
) -> str:
    """Send a prompt to OpenAI, optionally with the web-search tool.

    Faithful port of the notebook ``call_openai`` (STEP 3): same request shape and
    rate-limit retry behavior (retry only on ``RateLimitError`` with ``90 * attempt``
    second waits; ``APIError`` re-raises immediately; ``RuntimeError`` once retries are
    exhausted). ``client`` / ``model`` / ``sleep_fn`` are injected.

    Empty-output guard (item 8): a reasoning model on a rich topic can burn its output
    budget on web_search + reasoning and emit NO summary text -> ``output_text == ""``.
    Left silent, that blank is stored as an apparent "no evidence" finding. Instead: if the
    output is blank (empty or whitespace-only), retry ONCE at a bumped budget (×1.5 — to
    counter the budget-exhaustion *cause*, not re-roll identically); if STILL blank, return
    an explicit ``SEARCH_FAILED_MARKER`` — never a silent "" and never the false "none
    found" sentinel. Failure must not collapse into apparent absence.
    """

    def _attempt(tokens: int) -> str:
        for attempt in range(1, max_retries + 1):
            try:
                kwargs = {
                    "model": model,
                    "input": prompt,
                    "max_output_tokens": tokens,
                }

                if use_web_search:
                    kwargs["tools"] = [{"type": "web_search"}]
                    kwargs["tool_choice"] = "auto"

                response = client.responses.create(**kwargs)
                return response.output_text

            except RateLimitError:
                wait_time = 90 * attempt
                logger.warning(
                    "Rate limit hit. Waiting %s seconds before retry %s/%s...",
                    wait_time,
                    attempt,
                    max_retries,
                )
                sleep_fn(wait_time)

            except APIError as exc:
                logger.error("API error: %s", exc)
                raise

        raise RuntimeError(
            "Max retries reached. Try again later or reduce the company batch size."
        )

    text = _attempt(max_output_tokens)
    if str(text or "").strip():
        return text

    bumped = int(max_output_tokens * 1.5)
    logger.warning(
        "Empty model output at %s tokens; retrying ONCE at bumped budget %s.",
        max_output_tokens,
        bumped,
    )
    text = _attempt(bumped)
    if str(text or "").strip():
        return text

    logger.error("Empty model output after bumped retry; returning SEARCH_FAILED_MARKER.")
    return SEARCH_FAILED_MARKER


# =============================================================================
# STEP 4 - Raw research functions (verbatim prompts; web search enabled)
# =============================================================================


def search_funding(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    prompt = f"""
Use live web search to find the latest credible funding, valuation, stage, investors, and company maturity signals for:

{research_query}

Look specifically for:
- EACH priced funding round WITH ITS DATE and amount (e.g. "Series C, $40M, 2022; Series D, $90M, 2024")
  -- the full dated sequence, not just a single "stage". Note any bridge / extension / SAFE / convertible
  / debt events too (with dates), but mark them as such -- they do NOT redefine the stage bucket.
- total funding
- valuation
- named investors
- founding year (when the company was founded)
- major acquisitions or strategic investments
- IPO / S-1 / public-listing status (with the IPO/filing date)
- evidence that funding supports growth versus survival

Important:
- Prefer company announcements, SEC filings, Crunchbase/PitchBook summaries, TechCrunch, Forbes, Business Insider, Fierce Healthcare, MobiHealthNews, Healthcare Dive, STAT, Rock Health, or reputable investor/VC pages.
- Do not overstate uncertain funding information.
- If source quality is weak, say so.

Return a concise, sourced FACT LIST covering, where available: the DATED funding-round sequence (EACH
round with its date, amount, and whether it is a priced equity round vs a bridge / extension / SAFE /
debt event); any IPO / public-listing event with its date; total funding to date; valuation; and
founding year. Tag each fact with its source name and date. GATHER every round (including undated ones,
marked date-unknown) -- do NOT compute or pick a single funding_stage; a deterministic rule downstream
selects it from the rounds you gather.
If a particular fact is not found, say so rather than guessing.
If no credible public funding evidence exists at all, say "No strong public funding evidence found."
Do not invent figures.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=700
    )


def search_payer_signal(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    prompt = f"""
Use live web search to find whether the company has payer, employer, provider, health-system, benefits, pharma, government, or other institutional distribution traction for:

{research_query}

Look specifically for:
- payer contracts
- commercial insurance coverage
- Medicare / Medicaid / CMS activity
- employer benefits distribution
- provider / health system partnerships
- benefits platform partnerships
- pharma/life sciences partnerships
- channel partnerships that appear to drive adoption, utilization, covered access, or revenue
- named customers, covered lives, employer clients, health plans, providers, clinics, or systems
- evidence that the company has a durable institutional distribution path

Important:
- Distinguish a real distribution channel from a PR partnership or pilot.
- One named partnership is useful but should not be overstated as broad institutional traction.
- If the company is mostly D2C/cash-pay, say that clearly.
- If there is no payer/employer/provider signal, say so.

Return a concise, sourced summary of the institutional-distribution signal.
Include source name and date when available.
If none found, say "No strong public institutional signal found."
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=700
    )


def search_outcomes(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    prompt = f"""
Use live web search to find credible outcomes, clinical, behavioral, engagement, retention, utilization, or user-impact evidence for:

{research_query}

Look specifically for:
- peer-reviewed clinical outcomes
- published real-world evidence
- clinical trials
- patient/user outcomes
- engagement or retention metrics
- utilization metrics
- behavior-change evidence
- satisfaction/NPS if paired with substantive usage or outcome data
- evidence that the product creates durable user/patient/customer value

Important:
- Distinguish clinical outcomes from marketing claims.
- Distinguish user engagement from actual health outcomes.
- Small pilots, testimonials, and company-only claims should be treated as weak evidence unless supported by specific metrics.
- If evidence is limited, say so.

Return a concise, sourced summary of the outcomes signal.
Include source name and date when available.
If none found, say "No strong public outcomes evidence found."
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=700
    )


def search_commercial_scale(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    prompt = f"""
Use live web search to find whether the company has evidence of commercial scale, revenue quality, paid-user scale, or durable growth mechanics for:

{research_query}

Look specifically for:
- company-reported revenue, ARR, run-rate, GMV, sales, transaction volume, or bookings
- credible third-party estimated revenue or revenue run-rate
- credible private-market intelligence sources such as Sacra, The Information, Business Insider, Forbes, PitchBook summaries, CB Insights summaries, or investor reports
- paid users, subscribers, members, customers, covered lives, active accounts, renewals, or retention
- year-over-year revenue growth, subscriber growth, customer growth, or cohort expansion
- renewal rate, churn, retention, repeat purchase, repeat usage, or longitudinal engagement
- pricing power, annual subscription pricing, add-on revenue, device + subscription model, or high willingness to pay
- gross margin, scalable margin structure, CAC efficiency, organic demand, waitlist conversion, referrals, or operating leverage
- implied annualized revenue from paid customers × pricing, when direct ARR is not disclosed
- evidence that D2C/cash-pay scale can work without payer/employer/provider distribution
- evidence that institutional channels reduce CAC or improve revenue durability

Important:
- Clearly distinguish company-reported ARR/revenue from third-party estimated revenue/run-rate.
- Credible estimated revenue/run-rate should count as a real commercial-scale signal, but label it as estimated.
- Do not dismiss paid-customer scale just because ARR is not company-reported.
- Do not over-credit funding, valuation, brand heat, waitlist, downloads, traffic, or vague “fast-growing” claims unless tied to paid usage, retention, revenue, or durable distribution.
- If revenue is inferred from customer count × pricing, say it is implied/inferred and explain the caveat.
- If evidence is only marketing language or traffic estimates, say evidence is weak.

Return a structured list of the commercial-scale facts you find. For EACH figure include:
- the value, with the date or period it refers to
- the SOURCE TYPE: company-reported / third-party estimate (name the source and its method, e.g. Sacra) / promotional or unattributed
- where available, the TREND or history (e.g. "200k subscribers, up from ~50k in 2023"), not just a point-in-time snapshot
Cover, where available: revenue / ARR / run-rate; paid users / subscribers / members; pricing and the implied revenue-per-user (state the inputs); year-over-year growth; the business model (consumer subscription / enterprise / payer-reimbursed / other); and any funding context.
If a dimension is not found, say so. If no credible commercial-scale evidence exists at all, say "No strong public commercial scale evidence found."
Do not invent figures.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=700
    )


# =============================================================================
# STEP 4b - Operator / organizational searches (Slice 3.7; web search enabled)
# =============================================================================


def search_org_events(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    """Slice 3.7: recency-bounded current-events search for reset / restructuring events.

    Feeds ``reset_evidence.reset_events``. The fit-brief synthesis still emits the
    canonical structured field; this search supplies the multi-event *evidence*. Web
    search ON; larger token budget for a multi-item list so a quiet restructuring is
    not buried by a louder pivot (the ZOE finding that motivated Slice 3.5).
    """
    prompt = f"""
Use live web search to find RECENT leadership, restructuring, and transformation events for the
company below — signals that it may be at a high-agency inflection point where a senior operator
could step in and shape direction:

{research_query}

FOCUS ON THE LAST 12–18 MONTHS. A reset is a present-moment opening; a change from several years
ago is not a current opening and should be excluded unless it is still actively unfolding now.

Look for each DISTINCT event of these types:
- leadership-change — new CEO / C-suite / senior exec hired or departed
- founder-transition — founder stepping back or handing off to professional management
- declared-transformation — a publicly stated turnaround, "new chapter," strategic reset, or re-foundation
- post-failure-rebuild — rebuilding after a setback, near-miss, failed launch, or down round
- restructuring-layoffs — reorganization, layoffs, or restructuring (especially framed as refocusing or building toward a next phase)
- strategic-pivot — a material change in business model, market, or product direction
- ma-integration — a merger, acquisition, or post-deal integration

Important:
- List EACH distinct event SEPARATELY. A company can be doing several at once — e.g. a loud
  product pivot AND a quieter restructuring. Do NOT collapse them into one event, and do NOT let
  a prominent event hide a co-occurring one.
- For each event, judge whether it creates a HIGH-AGENCY OPENING: a forward-build mandate where a
  new operator could own meaningful direction (yes), versus a purely defensive, cost-cutting, or
  already-settled change (no), or genuinely unclear (unclear).
- Weight COSTLY, REVEALED actions (an actual CEO/exec change, a real reorg or layoff,
  a completed acquisition) OVER the company's own FRAMING of itself. A press release
  branding a routine change as a "transformation" or "new chapter" is weak evidence;
  a structural event that actually happened is strong. Do not log PR language as an
  opening unless a real underlying event backs it.
- Recency is decisive — give the date and prefer events within ~18 months.
- Distinguish a real, sourced event from rumor or routine corporate news.

Return a LIST — one item per distinct qualifying event. For EACH event give:
- event_type (one of the types above)
- what happened, with date and source name
- one sentence on whether it creates a high-agency opening (yes / no / unclear) and why
If there are no qualifying recent events, say exactly: "No qualifying recent org/leadership events found."
Do not invent events.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=800
    )


def search_operating_characteristics(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    """Slice 3.7: gathers product-engagement + operational-strain evidence.

    Feeds capability-fit A1/A2/A3, which are *scored* in Slice 4 — this slice only
    gathers and persists the evidence and adds no capability output fields. Web search
    ON; larger token budget for the structured, multi-item, strength-tagged output.
    """
    prompt = f"""
Use live web search to assess TWO things about how the company below actually operates:
(A) whether its product depends on habitual, high-frequency user engagement, and
(B) whether it shows signs of OPERATIONAL STRAIN from scaling.
{research_query}

These are evidence-from-behavior questions. What people DO and what the company
STRUCTURALLY does reveal the truth; company marketing only CLAIMS it.

────────────────────────────────────────────────────────
(A) PRODUCT-ENGAGEMENT STRUCTURE
For ENGAGEMENT evidence (frequency, user habit), weight independent signals
(app-store reviews, user discussion, third-party usage data) OVER the company's
self-description — how engaged users actually are is something they reveal, not
something the company can credibly claim.
For REVENUE-STRUCTURE evidence, the company's own disclosures (pricing pages,
business model, plan tiers, earnings) ARE reliable — revenue structure is a
verifiable structural fact, not a self-flattering claim.
Look for:
- FREQUENCY: Is the product used daily / at high frequency (a genuine habit loop),
  or periodically / occasionally? Cite behavioral evidence, not marketing.
- USER HABIT: Do users report habitual reliance — retention figures, repeat-usage
  patterns, reviews describing daily use or withdrawal when they stop?
- REVENUE DEPENDENCE: Map the FULL revenue structure, including BOTH one-time and
  recurring components if both exist. Distinguish:
    • recurring revenue that COLLAPSES without sustained engagement (e.g. a monthly
      or annual subscription that is the user's whole spend), versus
    • one-time or transactional revenue that is captured up front and does NOT depend
      on the user staying engaged (e.g. a hardware purchase, a one-off fee).
  Many companies are HYBRID — e.g. a one-time device purchase PLUS an ongoing
  membership. When so, report BOTH components and, if findable, the rough split or
  relative size of each. Do not collapse a hybrid model into "has a subscription";
  the one-time portion dilutes retention-dependence and that distinction matters.
If engagement is clearly periodic/optional, or revenue does not depend on it, say so
plainly — that is a valid, informative finding.

────────────────────────────────────────────────────────
(B) OPERATIONAL STRAIN
The signal is strain — things BREAKING under growth — NOT the mere existence of
complexity. Every competitive company is complex; that is not a signal. Look for two
DIFFERENT kinds of evidence and keep them distinct:

  (B1) STRUCTURAL / FACTUAL signals — these are objective and carry weight on their own:
  - SPEED OF SCALE: headcount growth rate (e.g. ~100 → ~500 employees in ~6 months),
    rapid office/market expansion. Report the numbers and dates; fast scaling is itself
    a strong strain signal.
  - layoffs, restructuring, or reorganizations — especially framed as "grew too fast"
    or a correction to over-hiring
  - hiring scrambles for senior operators or "first head of X" roles, which signal a
    capability gap the company is racing to fill

  (B2) REPORTED / EXPERIENTIAL signals — softer; apply a STRICT bar:
  - Count these ONLY when MULTIPLE INDEPENDENT sources describe the SAME specific
    breakdown (e.g. several people independently citing broken onboarding, missed
    launches, fulfillment failures, leadership churn).
  - Prefer candid discussion venues (Reddit, industry forums, independent reporting)
    over reviews that are easily gamed or one-off.
  - Do NOT count routine individual griping (one bad manager, low pay, generic
    "disorganized") — that exists at every company and is NOT a strain signal.

Important:
- Distinguish the company's STRUCTURAL ACTIONS (layoffs, reorgs, senior hires — strong,
  because they are costly and revealed) from the company's CHARACTERIZATIONS of itself
  ("we're scaling smoothly" — weak).
- ABSENCE of strain is itself a finding. Default to reporting LOW / no strain unless
  strain is clearly demonstrated by the bar above. A smoothly-scaling company should be
  reported as "No notable operational strain found." Do NOT manufacture strain.

────────────────────────────────────────────────────────
OUTPUT FORMAT
Return a structured list of evidence items, grouped under three headings. For EACH item give:
  - claim: one sentence stating the specific fact or finding
  - source: source name + date
  - strength: STRONG (structural/factual, or multiple independent sources) /
    MODERATE (one solid source) / WEAK (single soft mention)

"Product-engagement:"
  [evidence items for A — or "Engagement is periodic/optional: <why>" if that's the finding]
"Operational strain — structural:"
  [B1 items — or "None found." ]
"Operational strain — reported:"
  [B2 items meeting the strict bar — or "None meeting the bar found." ]

Cite a source and date for every item. Distinguish independent evidence from company
claims. Do not invent figures or events.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=800
    )


# =============================================================================
# STEP 4c - Search recovery: always-run-N + union on web-search variance
# =============================================================================
#
# Web search is nondeterministic: a single pass coin-flips on whether it reaches
# the page that holds a figure (see audits/research_revenue_cause_isolation_findings.md
# -- Midi revenue 2/5 byte-identical tries; Solace 5/5; Pelago 0/5, genuinely
# absent). ``search_with_recovery`` is the field-agnostic fix: run a FIXED N passes
# on every company and UNION all results. Pass 1 is the proven general search;
# passes 2..N are source-directed (lead, not filter). There is NO conditional stop,
# so the retry layer makes NO quality judgment -- quality is rated entirely
# downstream by the fit-brief synthesis (evidence_confidence_score / q4).
# ``call_openai`` is untouched; its blank-guard still protects each individual pass.
# Spec: specs/search_recovery_retry_union_spec.md.


@dataclass
class RecoveryProvenance:
    """Observability-only record of one recovery run. Gates nothing and judges no
    quality. ``figure_present`` is the single end-of-union presence check (the only
    presence role left once stop-on-hit is gone); it feeds logging and the Mode-B
    cross-check (the union held a figure the synthesis later left empty). ``passes``
    holds the raw per-pass findings so callers (the live-validation harness) can SEE
    pass independence — if the passes come back near-identical, the inter-pass
    cadence is too tight and the variance is not actually varying."""

    field_name: str
    n_passes: int
    figure_present: bool
    passes: list = field(default_factory=list)


def _union_findings(findings) -> str:
    """Concatenate labeled ``(label, text)`` pass findings, preserving everything.
    Conflicting figures are NOT collapsed -- the synthesis adjudicates (Rule 7)."""
    return "\n\n".join(f"--- {label} ---\n{text}" for label, text in findings)


def search_with_recovery(
    search_fn,
    research_query,
    *,
    client,
    model: str = DEFAULT_MODEL,
    retry_prompt_builder,
    presence_check,
    field_name: str,
    n_passes: int = 5,
    wait_between_passes: float = 0.0,
    sleep_fn=time.sleep,
):
    """Run ``n_passes`` web searches and UNION the results -- the field-agnostic
    recovery mechanism (no early stop; every company gets all N passes).

    * Pass 1 calls ``search_fn(research_query, client=, model=)`` verbatim (the
      proven general search).
    * Passes 2..N call ``call_openai`` with ``retry_prompt_builder(research_query)``
      (source-directed; web search ON), each preceded by a ``wait_between_passes``
      sleep so rapid-fire identical queries don't return correlated / cached result
      sets that would defeat the execution variance this mechanism depends on.
      ``wait_between_passes`` should be NON-ZERO in production; the 0.0 default is for
      unit tests / direct callers that inject their own cadence (production wiring
      passes ``DEFAULT_WAIT_BETWEEN_PASSES``).
    * Passes that returned ``SEARCH_FAILED_MARKER`` or blank contribute NOTHING to
      the union. If EVERY pass failed, ``SEARCH_FAILED_MARKER`` is returned so
      downstream ``is_search_failure`` still tells a failed search apart from a
      genuine no-figure finding.
    * ``presence_check(union_text, client=, model=) -> bool`` is OBSERVABILITY ONLY
      (provenance + Mode-B cross-check): it gates nothing and judges no quality.

    ``search_fn`` / ``retry_prompt_builder`` / ``presence_check`` / ``field_name``
    are per-field config, so adding a field is configuration, not a rewrite. The raw
    per-pass findings are returned in ``RecoveryProvenance.passes`` so a caller can
    inspect pass independence. Returns ``(union_text, RecoveryProvenance)``.
    """
    if n_passes < 1:
        raise ValueError("n_passes must be >= 1")

    findings = [
        ("pass1 (general)", search_fn(research_query, client=client, model=model))
    ]
    for p in range(2, n_passes + 1):
        if wait_between_passes:
            sleep_fn(wait_between_passes)  # let the search result set vary (avoid cache)
        text = call_openai(
            retry_prompt_builder(research_query),
            client=client,
            model=model,
            use_web_search=True,
            max_output_tokens=700,
        )
        findings.append((f"pass{p} (source-directed)", text))

    raw_passes = [text for _label, text in findings]

    real = [
        (label, text)
        for label, text in findings
        if str(text or "").strip() and not is_search_failure(text)
    ]
    if not real:
        # Every pass failed or was blank -> preserve the failure signal so the
        # union is not mistaken for a genuine "no figure found".
        return SEARCH_FAILED_MARKER, RecoveryProvenance(
            field_name=field_name,
            n_passes=n_passes,
            figure_present=False,
            passes=raw_passes,
        )

    union_text = _union_findings(real)
    figure_present = bool(presence_check(union_text, client=client, model=model))
    return union_text, RecoveryProvenance(
        field_name=field_name,
        n_passes=n_passes,
        figure_present=figure_present,
        passes=raw_passes,
    )


# ---------------------------------------------------------------------------
# Revenue config (the first instance of search_with_recovery)
# ---------------------------------------------------------------------------

# Per-field pass budget for revenue recovery (spec: N=5 -> ~92% worst-case recovery
# on the Midi p=.40 case; passes 2..N are source-directed so real recovery >= that).
REVENUE_RECOVERY_PASSES = 5

# Per-field pass budget for growth-rate recovery (always-run-N, never stop-on-hit). Sized from the
# post-refine-to-derive re-measure (FRAMEWORK_VERSION v1.1): worst RECOVERABLE case Midi 60% -> ~99%
# at N=5; ZOE 100%. Solace EXCLUDED from sizing -- genuine-absent for growth (one dated revenue
# point, consistent across passes; the qualitative floor catches it), not a recoverable blinker.
GROWTH_RECOVERY_PASSES = 5

# Per-field pass budget for paying-customer-count recovery (always-run-N). Re-measured clean
# (Tightening 2: paying employer-clients kept distinct from non-paying covered-lives; the Pelago
# stress case) -> N=5, matching the measurement -- its OWN paying-directed recovery, not riding on
# the revenue-directed commercial union. Built against FRAMEWORK_VERSION v1.2.
PAYING_RECOVERY_PASSES = 5

# Per-field pass budget for funding-ROUNDS recovery (always-run-N), source-directed for LATEST-round
# RECALL. LOCKED = 2 by the source-directed re-measure (audits/all_fields_probe_findings.md §14): per-pass
# recall is ~100% once source-directed (Sword's Series D/F was gathered in ALL 5 passes; the prior "60%"
# was a MAPPER artifact on non-canonical types, now fixed by the canonical-stage filter). So N=2 is a thin
# BUFFER on a GATE input (1 general + 1 source-directed, two shots at the latest round) -- NOT N=4
# (brute-forcing a non-problem), NOT N=1 (no margin on a gate signal). Built against FRAMEWORK_VERSION v1.2.
FUNDING_RECOVERY_PASSES = 2


def revenue_source_directed_prompt(research_query) -> str:
    """Source-directed retry prompt for passes 2..N of revenue recovery.

    Targets the financial-data sources that recurred across our recoveries
    (CB Insights / Latka / Growjo / PitchBook / Sacra) by constructing their canonical
    URLs directly (a per-pass reliability boost) AND by trying known aliases / former
    names (the Pelago/Quit Genius, "Join X" miss class). This is ADDITIVE, never a
    filter (Gate-2): it MUST still surface company-disclosed figures that live OUTSIDE
    aggregators -- press releases, crowdfunding (Crowdcube), founder interviews,
    statutory filings (Companies House) -- our own recoveries came through those. The
    pass-1 general prompt (``search_commercial_scale``) is unchanged; this only sharpens
    the retries. Issued with web search ON by ``search_with_recovery``."""
    return f"""
Use live web search to find REVENUE / ARR / run-rate evidence for:

{research_query}

START by going DIRECTLY to the financial-data sources that most often carry private-
company revenue figures and estimates. Construct and open their canonical pages from
the company's domain / name so you reliably land on pages we know exist:
- Latka: getlatka.com/companies/<company domain> (e.g. .../companies/pelagohealth.com)
- CB Insights: cbinsights.com/company/<company-name>/financials
- Growjo: its company page for the name AND for any former name
- PitchBook and Sacra: the company's profile page
Also try the company's KNOWN ALIASES and FORMER NAMES -- aggregators often list a
company under a former name or a brand alias (e.g. Quit Genius -> Pelago; a "Join X"
brand for X). If a page shows an entry that looks wrong for this company (absurd scale,
wrong employee count, wrong industry), treat it as a possible namesake and try the
alias / former name before concluding no figure exists.

This direct-URL targeting is IN ADDITION TO, NOT INSTEAD OF, the open search for
company-disclosed figures wherever they live. The aggregators are a LEAD, NOT a filter
-- you MUST ALSO surface company-disclosed figures that live OUTSIDE them, including:
- company press releases, newsroom posts, and blog announcements
- crowdfunding disclosures (e.g. Crowdcube, Wefunder) and investor / IR pages
- founder or executive interviews and conference talks
- statutory filings (e.g. Companies House) and reputable press citing a figure
Do NOT restrict the search to the aggregators above -- a real figure that lives only in
a press release, a crowdfunding round, or a statutory filing MUST still be returned.

For EACH figure include: the value with its date / period; the SOURCE TYPE
(company-reported / third-party estimate -- name the source and method / promotional);
and the trend or history if available. Clearly distinguish company-reported from
estimated figures. Include weak or single-source figures too -- label them weak; do
NOT omit a real figure for being low-quality. If no revenue figure is found in any
credible source, say "No revenue figure found." Do not invent figures.
"""


def _parse_presence(text) -> bool:
    """Parse a PRESENT / ABSENT verdict. Conservative: only an explicit PRESENT is
    True. This is observability-only, so a wrong guess gates nothing."""
    return str(text or "").strip().upper().startswith("PRESENT")


def revenue_presence_check(union_text, *, client, model: str = DEFAULT_MODEL) -> bool:
    """Observability-only end-of-union presence check for revenue (NO web search).

    Answers "did the union surface a real revenue figure?" for provenance / logging
    and the Mode-B cross-check. It makes NO quality judgment and gates nothing --
    quality is the synthesis's job (``evidence_confidence_score`` / ``q4``).
    Implied-from-pricing counts as PRESENT (a real, labeled signal)."""
    prompt = f"""
Read the research findings below and decide ONE thing: do they contain a real
REVENUE figure for the company -- revenue, ARR, run-rate, GMV, sales, or bookings
that a source actually stated or credibly implied (including a figure implied from
paying-customers x pricing)?

Do NOT count as revenue: funding rounds, total raised, valuation, or a list / sticker
price on its own. A weak or single-source revenue figure still counts as PRESENT --
quality is judged elsewhere, not here.

Answer with exactly one word: PRESENT or ABSENT.

Findings:
{union_text}
"""
    out = call_openai(
        prompt, client=client, model=model, use_web_search=False, max_output_tokens=64
    )
    return _parse_presence(out)


# ---------------------------------------------------------------------------
# Group 1 field configs (source-directed prompts + presence checks)
# ---------------------------------------------------------------------------


def growth_rate_source_directed_prompt(research_query) -> str:
    """Source-directed retry prompt for growth-RATE recovery (Group 1). Refine-to-derive: COMPUTES the
    rate from dated revenue endpoints the search finds (not just pre-stated rates), with mandatory
    show-the-inputs, because growth rates exist as RAW MATERIAL more often than as finished figures.
    Keeps Tightening 1 (usable only WITH a period), lead-not-filter + alias (B1), and tags computed
    rates DERIVED. Used on passes 2..N by search_with_recovery (web search ON); pass 1 = general
    search_commercial_scale, unchanged. (Matched unit with the growth_signal carry text + the
    growth_rate_presence_check derived-clause; ship together.)"""
    return f"""
Use live web search to find the company's QUANTIFIED revenue or PAID-user growth rate for:

{research_query}

A usable growth rate is a NUMBER WITH the time period it covers -- e.g. "287% in 2023",
"+53% YoY 2024", "10x from Series B (2021) to 2023". The word "growing" with no number does
NOT count.

This is REVENUE growth or PAID-user/subscriber/member growth ONLY. Do NOT report headcount/
employee/team growth, office or geographic expansion, partner/client-count growth, funding
growth, or total-user/download/MAU growth that is NOT specifically PAID users/subscribers/
members -- those are NOT the signal we need here.

[1] COMPUTE the rate -- don't just look for a finished one. Growth rates exist as RAW MATERIAL
(two or more dated revenue/ARR points) more often than as a pre-stated percentage. WHENEVER you
find two or more dated revenue figures for the company, COMPUTE the growth between them yourself
(e.g. Latka's "$0 in 2021 -> $115.9M in 2025"; a CEO's "$60M end-2024 -> $150M late-2025").
Report derived rates AND any pre-stated rates; do not limit yourself to pre-stated ones.

[2] SHOW THE INPUTS for every computed rate, inline -- ALWAYS. A derived rate MUST display the
endpoints and dates it was computed from, e.g. "~2.5x over ~9 months, computed from $60M
(Dec 2024) -> $150M (Sep 2025)". NEVER emit a bare derived number like "150% growth" with no
visible inputs -- a number with no inputs is uninterpretable and is not acceptable. Mark a
computed rate as DERIVED (vs a company-stated rate) so its provenance is clear.

[3] TIME PERIOD IS REQUIRED for any rate, stated OR derived:
- A relative figure ("doubled", "10x", "+53%") MUST carry the period it covers.
- Endpoints (a from->to) WITHOUT dates are NOT usable -- record "endpoints found, dates missing
  -- not a usable rate"; do not emit a dateless rate.
- If a rate is stated but its period is unclear, record "rate found, period unclear" -- do NOT
  assume a period.

[4] START by going directly to the pages that carry growth figures and dated revenue series
(construct the URLs), as a LEAD -- not a filter:
- Latka: getlatka.com/companies/<domain> (a revenue series by year -> compute the rate from it)
- Growjo: its company page for the name AND any former name
- CB Insights: cbinsights.com/company/<name>/financials
This is IN ADDITION TO, NOT INSTEAD OF, company-disclosed growth wherever it lives -- funding/
milestone press releases ("287% revenue growth in 2023"), founder/executive interviews (often
two dated revenue points), statutory filings (compute the rate; show inputs+dates). Try KNOWN
ALIASES / FORMER NAMES (e.g. Quit Genius -> Pelago; a "Join X" brand); if a page looks like a
wrong-entity namesake (absurd scale/industry), try the alias before concluding none.

For EACH growth figure give: the value (a stated rate, OR a derived rate WITH its endpoints+dates),
the PERIOD, and the SOURCE TYPE (company-reported / third-party estimate / DERIVED-by-you). If only
a qualitative "growing" with no number and no dated endpoints is found, say so explicitly:
"growth direction only, no quantified rate." Do not invent figures or fabricate dates.
"""


def growth_rate_presence_check(union_text, *, client, model: str = DEFAULT_MODEL) -> bool:
    """Observability-only: is a USABLE quantified growth rate present -- a numeric rate WITH a time
    period (Tightening 1)? A dateless relative figure, a from->to without dates, or a qualitative
    "growing" is NOT usable -> absent. No web search; gates nothing; makes no quality judgment."""
    prompt = f"""
Read the findings below. Is there a USABLE quantified GROWTH RATE -- a numeric rate WITH a clear time
period, EITHER (a) STATED (e.g. "287% in 2023", "+53% YoY", "10x since 2021"), OR (b) DERIVED from two
or more dated revenue endpoints with the inputs shown (e.g. "~2.5x over ~9mo, from $60M (Dec 2024) ->
$150M (Sep 2025)")?

A numeric rate WITHOUT a time period, a from->to WITHOUT dates, or a qualitative "growing" with no
number does NOT count -- those are ABSENT for a usable rate.

Employee/headcount growth, funding growth, partner-count growth, office expansion, or non-paying
user/download/MAU growth do NOT count -- only REVENUE or PAID-user/subscriber/member growth.

Answer with exactly one word: PRESENT or ABSENT.

Findings:
{union_text}
"""
    out = call_openai(
        prompt, client=client, model=model, use_web_search=False, max_output_tokens=64
    )
    return _parse_presence(out)


def paying_count_source_directed_prompt(research_query) -> str:
    """Source-directed retry prompt for PAYING customer-count recovery (Group 1). Paying-only: a
    PAYING employer/health-plan client counts and belongs HERE; "covered / eligible lives" are
    NON-paying reach (they belong to institutional-distribution), and the two coexist for the same
    company (Pelago: "100+ employer clients" AND "3.4M eligible lives") -- keep them DISTINCT
    (Tightening 2). Leads with where paid counts are disclosed (company press/about, interviews) plus
    aggregators, as a LEAD not a filter; alias-aware; non-paying counts are returned + LABELED (not
    dropped, so free-scale signal is preserved). Used on passes 2..N by search_with_recovery."""
    return f"""
Use live web search to find the company's PAYING customer / subscriber / member COUNT for:

{research_query}

We need a count of PAYING customers -- paid subscribers, paid members, or PAYING business/enterprise
clients (e.g. "100+ employer clients" that PAY for the product). EXCLUDE free users, trials, pilots,
waitlists, downloads, and registered (non-paying) users.

Keep these DISTINCT -- do NOT conflate them:
- PAYING entities (paid members, OR paying employer/health-plan clients) -> THIS field.
- "Covered / eligible lives" under those clients are NON-paying reach, NOT a paying count -> they
  belong to institutional-distribution, not here. A company can have BOTH at once (e.g. Pelago:
  "100+ paying employer clients" AND "3.4M eligible lives") -- report the paying-client count here
  and label the eligible-lives figure separately as NON-paying.

START where paid counts are usually disclosed:
- company press releases, newsroom, "about" / "impact" pages, milestone posts
  ("over 100,000 paying members"; "100+ employer clients")
- founder / executive interviews and conference talks
- credible press citing a company-disclosed paid count
IN ADDITION (not instead), check aggregators: Latka getlatka.com/companies/<domain>; Growjo;
CB Insights company pages. Try KNOWN ALIASES / FORMER NAMES and a "Join X" brand; if a namesake looks
wrong (absurd scale/industry), try the alias before concluding none.

For EACH count give: the value, the date, whether it is explicitly PAYING (vs free / covered-lives),
and the SOURCE TYPE. If only free / registered / covered-lives counts are found, RETURN them but
LABEL them NON-paying. Do not invent figures.
"""


def paying_count_presence_check(union_text, *, client, model: str = DEFAULT_MODEL) -> bool:
    """Observability-only: is a PAYING customer / subscriber / member / business-client count present?
    Free / trial / registered users and "covered / eligible lives" do NOT count. No web search;
    gates nothing; makes no quality judgment."""
    prompt = f"""
Read the findings below. Is there a count of PAYING customers -- paid subscribers, paid members, or
PAYING business/enterprise clients?

Do NOT count: free / trial / pilot / waitlist / registered (non-paying) users, app downloads, or
"covered / eligible lives" (eligible-but-not-paying reach under an employer/health-plan).

Answer with exactly one word: PRESENT or ABSENT.

Findings:
{union_text}
"""
    out = call_openai(
        prompt, client=client, model=model, use_web_search=False, max_output_tokens=64
    )
    return _parse_presence(out)


def funding_rounds_source_directed_prompt(research_query) -> str:
    """Source-directed retry for passes 2..N of funding-ROUNDS recovery (FRAMEWORK_VERSION v1.2). Fixes
    the recall gap -- a generic pass coin-flips on the MOST RECENT round (Sword's series-d dropped 2/4) --
    the B1 way: lead with the pages carrying COMPLETE, dated round histories (Crunchbase / PitchBook /
    company announcements), constructing URLs, AND try aliases / former names. ADDITIVE, never a filter.
    The LLM GATHERS rounds (the fit-brief synthesis structures them per c3779cc) and NEVER picks a stage
    (the deterministic mapper does). Issued with web search ON by search_with_recovery."""
    return f"""
Use live web search to find the company's COMPLETE, DATED funding-round history -- and ESPECIALLY its
MOST RECENT priced round -- for:

{research_query}

The single most important thing to get right is the LATEST round: a generic search often stops at an
older round and misses the most recent one (the recall gap this pass exists to close). START by going
DIRECTLY to the sources that carry full, dated round histories. Construct and open their canonical pages
from the company's domain / name:
- Crunchbase: crunchbase.com/organization/<company-name> (the funding-rounds section)
- PitchBook: the company's profile page
- Growjo / CB Insights / Tracxn: the company page for the name AND for any former name
- the company's OWN funding announcements / newsroom / press releases for each raise
Also try KNOWN ALIASES and FORMER NAMES -- aggregators often list a company (and its later rounds) under
a former name or brand alias (e.g. Quit Genius -> Pelago; a "Join X" brand for X). If a page looks wrong
for this company (absurd scale, wrong industry), treat it as a possible namesake and try the alias /
former name before concluding.

This direct-URL targeting is IN ADDITION TO, NOT INSTEAD OF, the open search for company-disclosed rounds
wherever they live -- press releases, investor / IR pages, reputable press citing a raise + date,
statutory filings. The aggregators are a LEAD, NOT a filter: a recent round announced only in a press
release MUST still be returned. Pay special attention to any round in the LAST ~24 MONTHS -- that is the
one a generic pass most often misses.

For EVERY round, report: its TYPE (seed / series-a / ... / series-d / ... / bridge / extension / SAFE /
convertible / debt), its DATE (year or year-month), its AMOUNT, and whether it is a PRICED EQUITY round
(seed/series-*) vs a bridge / extension / SAFE / convertible / debt event. Include undated rounds (mark
them date-unknown), and report the FULL dated sequence INCLUDING the most recent round.
Do NOT compute or pick a single funding_stage -- the deterministic rule downstream selects it from the
rounds you gather.
"""


def funding_latest_round_presence_check(union_text, *, client, model: str = DEFAULT_MODEL) -> bool:
    """Observability-ONLY: does the union contain a RECENT priced equity round WITH a date -- a PROXY for
    'the latest round was gathered'? No web search; gates NOTHING; changes only provenance (figure_present),
    never the union / pass count / the mapper's selection. We cannot verify the TRUE latest without ground
    truth, so ABSENT is a SOFT signal (recall-miss OR genuinely-no-recent-raise) that only FEEDS the gate
    fail-safe flag -- it never filters rounds or floors a company."""
    prompt = f"""
Read the funding findings below. Is there at least one PRICED EQUITY round (seed / series-a / series-b /
... / series-d+) reported WITH a date in roughly the LAST ~24 MONTHS -- a plausible MOST-RECENT round? A
round history that stops several years ago, or rounds with no date at all, does NOT count.

Answer with exactly one word: PRESENT or ABSENT.

Findings:
{union_text}
"""
    out = call_openai(
        prompt, client=client, model=model, use_web_search=False, max_output_tokens=64
    )
    return _parse_presence(out)


# =============================================================================
# STEP 5 - Company fit synthesis prompt
# =============================================================================


def load_taxonomy_prompt_block_for_fit_brief(taxonomy_dir) -> str:
    """Load controlled taxonomy instructions for the LLM fit brief.

    Faithful to the notebook wrapper's behavior: delegate to the package's
    ``build_taxonomy_prompt_block`` and fall back to the same instruction string
    if the taxonomy cannot be loaded. (The notebook's Colab ``/content`` sys.path
    bootstrap is dropped — inside the package the import is direct and the
    taxonomy directory is passed in.)
    """
    try:
        from .taxonomy import build_taxonomy_prompt_block

        return build_taxonomy_prompt_block(taxonomy_dir)
    except Exception as exc:  # noqa: BLE001 - faithful fallback to a usable prompt
        return (
            "CONTROLLED HEALTH-TECH TAXONOMY UNAVAILABLE. "
            "Still return taxonomy_classification using best effort. "
            f"Taxonomy load error: {exc}"
        )


def build_fit_brief_prompt(
    company_name, latest_status_findings, taxonomy_prompt_block
) -> str:
    """Build the company fit-brief prompt (byte-identical to notebook STEP 5).

    Pure function: no LLM call, no I/O. Splitting prompt construction from the
    call lets the prompt be asserted in tests without an API key, and gives the
    later slices a single in-package place to add structured fields.
    """
    return f"""
You are evaluating a health tech company for Katelynd LaVallee's job search.

Company:
{company_name}

Latest research findings:
{latest_status_findings}

Katelynd's background:
- Former VP of Product Development at Warner Bros. Discovery.
- 12 years at WBD; progressed from analyst to VP.
- Led complex consumer digital products, including mobile/live-service products.
- Managed $50M+ annual operating budgets and organizations of 200+.
- Strong in product strategy, product operations, data-informed decision-making, consumer insights, experimentation, lifecycle systems, retention/engagement, execution cleanup, operating-model design, and cross-functional alignment.
- Best-fit environments: complex, high-growth, data-rich products where product, operations, analytics, user behavior, and execution systems need to be connected.
- Targeting health tech companies where her consumer product/operator background can translate into leadership roles such as VP Product, VP Operations, GM, Chief of Staff to CEO/COO, Commercial/Product Ops, or similar executive operating roles.

Current job-search thesis:
- Prioritize health tech companies with meaningful patient/user outcomes, recurring engagement, measurable behavior change, data-rich products, and a credible path to scale.
- Path to scale can come from either:
  1. durable institutional distribution, such as payer, employer, provider, health-system, benefits, pharma, government, or B2B2C channels; OR
  2. exceptional commercial traction / revenue quality in a D2C or cash-pay model.
- D2C is not automatically bad. Unsupported D2C is risky. D2C with credible paid-customer scale, ARR/revenue, subscriber/member growth, renewal/retention, pricing power, repeat usage, or strong recurring monetization can remain highly relevant.
- Do not overvalue funding, valuation, brand heat, waitlists, downloads, app usage, pricing pages, or vague growth claims unless tied to paid usage, revenue quality, durable distribution, retention, or outcomes.

Preferred stage and role-agency thesis:
- Katelynd is not primarily looking for a mature enterprise-scale health tech company that already has professionalized executive layers, well-developed operating systems, and narrow leadership lanes.
- Her highest-fit target is a Series A/B or early Series C company with early product-market fit signs that now needs to scale from early traction toward $100M ARR.
- The company should have enough traction to prove the market is real, but still enough operating ambiguity that a senior product/operator can materially shape the business.
- Mature companies can still be useful benchmarks or role-scope-dependent targets, but they should not receive high operator timing scores unless there is specific evidence of high-agency whitespace, a major operating rebuild, a new business line, or unusually immature operating systems relative to revenue/stage.

Core PMF / scale scoring rule:
For pmf_scale_score, DO NOT average commercial traction and institutional distribution as if both are required.

Instead:
- Treat revenue quality / commercial traction and payer-employer-provider distribution as alternative primary scale engines.
- A company can have a strong PMF/scale signal if EITHER:
  - commercial traction is strong, such as credible revenue, ARR, run-rate, paid users, subscribers, customer/member growth, renewal, retention, pricing power, repeat usage, or credible third-party estimated revenue/run-rate; OR
  - distribution durability is strong, such as payer, employer, provider, benefits, health-system, pharma, government, or B2B2C adoption.
- If BOTH commercial traction and institutional distribution are strong, score materially higher.
- Outcomes / product-value evidence is a validation layer. Strong outcomes evidence strengthens PMF/scale because it suggests durable value. Weak outcomes evidence should create a diligence caveat, but it should NOT erase a strong revenue or distribution scale engine.
- Evidence confidence is separate. If revenue is credible but estimated, PMF/scale can rise, while evidence_confidence_score should remain moderate rather than high.

Private-company evidence caveat:
- For private companies, retention, renewal, churn, CAC, gross margin, payback period, and cohort behavior are often not publicly disclosed.
- Do not heavily penalize a private company simply because those internal operating metrics are unavailable.
- Missing internal metrics should create a durability caveat and may lower evidence_confidence_score, but should not automatically cap pmf_scale_score if there is credible revenue/run-rate, paid-customer scale, subscriber/member growth, or institutional distribution evidence.
- Credible estimated revenue/run-rate from sources such as Sacra, The Information, Business Insider, Forbes, PitchBook summaries, CB Insights summaries, or investor materials can support a strong PMF/scale signal, as long as the output clearly labels the figure as estimated rather than company-reported.

PMF / scale interpretation guide:
- Strong revenue/commercial traction + weak institutional channel + weak outcomes = medium-high PMF/scale, not low.
- Weak revenue/commercial traction + strong institutional channel + weak outcomes = medium-high PMF/scale, not low.
- Strong revenue/commercial traction + strong institutional channel + weak outcomes = high PMF/scale.
- Strong revenue/commercial traction + weak institutional channel + strong outcomes = high PMF/scale.
- Weak revenue/commercial traction + strong institutional channel + strong outcomes = high PMF/scale.
- Strong revenue/commercial traction + strong institutional channel + strong outcomes = very high PMF/scale.
- Weak revenue/commercial traction + weak institutional channel + strong outcomes = low to medium PMF/scale unless there is also a plausible near-term commercial or institutional scale path.
- Weak revenue/commercial traction + weak institutional channel + weak outcomes = low PMF/scale.

PMF / scale score bands:
- 90-100: Very strong PMF/scale. Requires multiple strong signals, such as strong commercial traction plus strong institutional distribution, or one exceptional scale engine plus strong outcomes/product-value evidence.
- 80-89: Strong PMF/scale. Use when there is one strong scale engine plus meaningful supporting evidence from outcomes, retention/engagement, secondary distribution, customer growth, pricing power, renewal, or repeat usage.
- 70-79: Strong but incomplete PMF/scale. Use when one scale engine is clearly strong and specific, even if outcomes evidence or the secondary scale engine is weak. This is appropriate for private companies with credible estimated revenue/run-rate and paid-customer scale, but missing internal operating metrics.
- 60-69: Medium PMF/scale. Use when one scale engine is credible but incomplete, or when several moderate signals point in the right direction.
- 40-59: Weak-to-moderate PMF/scale. Use when there are interesting signals but no clearly proven scale engine.
- 0-39: Weak PMF/scale. No clear commercial traction, distribution durability, or outcomes/product-value proof.

PMF / scale guardrails:
- Do not score above 80 based only on funding, valuation, brand awareness, celebrity buzz, waitlist, downloads, pricing pages, or vague “fast-growing” claims.
- Do not score above 80 based only on estimated revenue unless there is also evidence of paid-customer growth, subscriber/member scale, pricing power, repeat usage, retention/engagement, institutional distribution, or outcomes/product-value durability.
- Do not require payer/employer/provider distribution for a high PMF/scale score if the company has strong commercial traction.
- Do not require D2C revenue quality for a high PMF/scale score if the company has strong institutional distribution.
- Pricing alone, a membership model alone, a waitlist alone, funding alone, or role-fit relevance alone is not enough to establish strong PMF/scale.

Maturity evidence — gather FACTS ONLY. Do NOT output a maturity label OR a funding_stage; the system
derives BOTH deterministically (a code mapper picks funding_stage from the rounds; maturity from
funding_stage + ipo_status).
- funding_rounds = GATHER every funding round you can source, each with its type, date, amount, and
  is_priced_equity (priced equity vs bridge/extension/SAFE/convertible/debt). Include undated rounds
  with date "unknown". Do NOT pick a single stage and do NOT infer rounds from headcount, revenue,
  valuation, or "feel" — the deterministic mapper selects the stage (public-outranks; else latest-dated
  priced round) from what you gather.
- ipo_event = {{"occurred": true/false, "date": ...}} for a real IPO / public-listing event.
- ipo_status = "public" if shares trade publicly; "filed" ONLY if an S-1 / IPO registration is publicly filed but shares are not yet trading; otherwise "private".
- Revenue, ARR, valuation, and growth do NOT determine maturity — capture those under commercial_evidence. A Series B company with large revenue is still a series-b round (NOT a higher stage).
- funding_stage_evidence: cite the source + date for the funding rounds and IPO status.

Commercial evidence — gather FACTS and answer the four red-flag questions. Do NOT output a commercial strength label; the system derives the 0-3 commercial signal deterministically.
- Capture revenue/ARR and PAYING-customer counts with sources. Exclude free users, trials, pilots, and waitlists from paying_customer_count.
- List every revenue/ARR/run-rate figure that a source actually STATED, or that is implied from paying-customers × pricing — including weak or single-source figures. Do NOT omit a real figure for being low-quality; quality is captured by evidence_confidence_score and q4, never by exclusion here. Leave the field empty only if NO real figure was found in any pass.
- revenue_per_user: prefer a company-stated figure; otherwise COMPUTE it from figures already recovered -- revenue ÷ paying-customer count, or annual pricing -- and SHOW THE INPUTS inline, e.g. "~$500/yr, computed from ~$100M revenue ÷ ~200k paying members" or "from $29/mo pricing x 12". Mark a computed value DERIVED (not company-reported). Leave empty only if neither a stated figure nor the inputs to derive one are available. Never emit a bare per-user number with no inputs.
- ENTITY-DOUBT handling for a revenue figure whose source name/domain you are NOT certain is THIS company:
  - PLAUSIBLE alias (same or adjacent name; a brand alias or "Join X" / joinX.com matching the company's own domain root; or a known former name) -> CARRY the figure in revenue_or_arr, tag it inline "(entity-uncertain: possible alias of <company> -- verify)", set "entity_review_needed": "possible-alias", note it in unverified_or_weak_claims, and keep evidence_confidence_score moderate-to-low. NEVER silently omit it.
  - CLEAR mismatch (a different industry/business, a clearly different named company, or a scale implausibly off -- e.g. orders of magnitude below the company's corroborated scale) -> EXCLUDE it as wrong-entity and say so in unverified_or_weak_claims.
  - When genuinely unsure which applies, PREFER carry+flag over silent drop: a flagged figure is reviewable; a dropped one is invisible.
- funding_evidence is context ONLY. Funding raised and valuation are NOT commercial traction and are structurally excluded from the signal — do not let them influence q1/q2.
- The commercial research section now tags each figure with a SOURCE TYPE (company-reported / third-party estimate / promotional) and, where available, a TREND/history; read q4_evidence_quality off those SOURCE TYPE tags and read q1_acquisition off the TREND. Still answer q1-q4 here as defined below — the search only supplies richer evidence, it does not move where these are judged.
- q1_acquisition: direction of the PAYING base (growing / flat / declining).
- q2_monetization: revenue-per-user vs. what is normal FOR THIS business model (strong / typical / weak).
- q3_funding_dependent: "yes" if, setting the funding/valuation story aside, the real commercial evidence (revenue + paying customers) would be thin. (Explicit funding-as-commercial catch.)
- q4_evidence_quality:
  - "company-reported" = the company disclosed the figure;
  - "credible-estimate" = a named reputable third party with a methodology (Sacra, CB Insights, reputable press citing sources);
  - "unverified-promotional" = the company's own marketing, vague "fast-growing", or figures with no attributable source.
  - When MULTIPLE revenue figures are present, set q4_evidence_quality to the STRONGEST quality among them: "company-reported" if any figure is company-reported; else "credible-estimate" if any is a named third-party estimate; else "unverified-promotional". Multiple weak or single-source figures do NOT promote q4 — if no figure is company-reported and none is a credible third-party estimate, q4 stays "unverified-promotional" however many weak figures exist. (More corroboration may raise evidence_confidence_score, but it NEVER lifts q4's source-type bucket.)

Reset / restructure evidence — capture whether the company is in a moment of organizational disruption that creates a HIGH-AGENCY ENTRY OPENING for a senior operator (whitespace + a forward-looking mandate to BUILD) — NOT about strategy or health, and NOT a reward for any change that merely looks disruptive.
A company may be doing SEVERAL of these at once. List EACH distinct event as its own object in reset_events, answer the opening question PER EVENT on its own terms, and do NOT let one event's nature determine another's. If you find no reset/restructure events, return an empty list [].

CLASSIFY BY SUBSTANCE, NOT PRESS FRAMING. Judge each event on what ACTUALLY changed, never on the company's label for it. "Transformation," "evolution," "pivotal," "next chapter" are marketing words — they do not decide event_type. You are the single emitter: classify event_type and read the opening from the underlying facts, even when that means re-classifying how the source framed it. (The per-event reads in the "Recent org / leadership events" findings are inputs to weigh, not labels to transcribe.)

For each event:
- event_type — choose by SUBSTANCE:
  - leadership-change — a new CEO / senior exec brought in to BUILD or TURN AROUND the company (a reopened operating window). NOT a routine functional hire to staff ongoing growth (see the opening rule).
  - founder-transition — founder stepping back / bringing in professional leadership to scale.
  - post-failure-rebuild — rebuilding after a stumble, with a forward mandate.
  - restructuring-layoffs — restructuring / layoffs. EITHER a rebuild-toward-growth OR a contraction-toward-decline — do NOT prejudge it; the opening question for THIS event decides.
  - declared-transformation — an OPERATING-MODEL rebuild: rebuilding HOW the company runs INTERNALLY (its operating systems, org, processes). Reserve STRICTLY for an internal operating rebuild. A change to WHAT the company sells, its product line, its pricing, or its go-to-market is NOT this.
  - strategic-pivot — a change to the BUSINESS MODEL, PRODUCT STRATEGY, PRICING, or GO-TO-MARKET: e.g. D2C -> payer / B2B; a new product category or an "evolution" into a different kind of product; a pricing-model change (engagement-based -> outcome-based); expansion into a new clinical / product area. This is strategic-pivot EVEN IF framed as a "transformation," "evolution," or "pivotal" moment. ("Changed/added what we sell or how we price/sell it" = strategic-pivot; "rebuilding how we operate internally" = declared-transformation.)
  - ma-integration — merger / acquisition integration work.
  - ipo-prep — IPO preparation: an S-1 / draft (incl. confidential) registration statement, public-market-readiness, or "going public" activity. A MATURE-TRAJECTORY event, the OPPOSITE of a reopened build-window. Classify ALL IPO / S-1 / public-market-readiness events here, even when framed as a "transformation" or "next chapter."
- basis — cite the source + date for THIS event.
- creates_high_agency_opening — for THIS event, by HONEST confidence:
  - "yes" ONLY when THIS event CLEARLY reopens a high-agency window (the company is actively rebuilding / turning around and needs a senior operator to BUILD). Do NOT round up to "yes" when uncertain.
  - "no" when THIS event is a DEFENSIVE reaction (a pivot under pressure, a contraction toward survival/decline, routine integration) or a MATURE-trajectory event (ipo-prep).
  - "unclear" when the evidence doesn't let you tell.
  - EXEC ADD — read the opening by STRUCTURAL ROLE, not the company's growth framing: a senior exec ADDED to SUPPORT / DRIVE / SCALE an existing growth / expansion / partnerships / commercial motion (a CMO, CRO, or similar growth / commercial hire — "expanding the executive team" to fuel growth) -> "unclear". This is the common scaling-company case and is NOT a reopened build-window, EVEN when the title is senior. Emit "yes" for an exec add ONLY for a CLEAR structural reset — a NEW CEO replacing the prior CEO, a founder stepping back for professional leadership, OR a FIRST-EVER / NEWLY-CREATED C-suite seat that stands up a function the company did NOT previously have (e.g. its FIRST CFO building finance / operating discipline). The test: does this BUILD a missing operating function (-> "yes") or STAFF an existing growth thrust (-> "unclear")?
  - Example: a company that (a) shifts its model under pressure [strategic-pivot, opening=no] AND (b) restructures to fund a rebuild toward expansion [restructuring-layoffs, opening=yes] — list BOTH; the restructuring's "yes" stands on its own.
(The deterministic rule downstream fires ONLY when event_type is a firing type AND creates_high_agency_opening == "yes". strategic-pivot, ma-integration, and ipo-prep NEVER fire; "unclear" / "no" never fire; multiple "unclear" events do NOT sum to a fire. Your job is an honest per-event SUBSTANCE classification + an honest opening read — the deterministic code decides what fires.)

Capability-fit — score THREE company-SHAPE attributes (A1, A2, A3), each 0-100 within the
bands below, each with a one-line basis. These measure how closely the company matches the
SHAPE of company where a senior consumer-product operator is exceptional — NOT whether specific
skills apply and NOT whether there is a mandate (those are scored elsewhere; do not import them
here). The system averages the three deterministically into katelynd_capability_fit_score — you
provide the three scores + bases, NOT the average. Draw primarily from the "Operating
characteristics" research section above (and its STRONG/MODERATE/WEAK strength tags), where
available.

Bands (apply to every attribute):
- Strong 85-100: clearly, centrally true of the company.
- Moderate 60-84: present, with caveats.
- Weak 30-59: mostly absent or only superficial.
- Absent 0-29: not characteristic at all.

- a1_score — PRODUCT-ENGAGEMENT STRUCTURE (data-driven by necessity). This is NOT a "do they
  have a data culture" question — that is unverifiable and companies self-describe it. It is a
  PRODUCT-STRUCTURE question: a product with a daily / high-frequency engagement loop whose
  REVENUE DEPENDS on sustained engagement is data-driven BY NECESSITY. Score HIGH when the
  product is habit-dependent AND revenue hangs on retention; LOW when engagement is
  periodic/optional, or revenue does not depend on it (one-time/transactional, or analytics
  feeding slow planning cycles rather than the product's own daily loop). Asymmetry: doing the
  data loop BADLY is the value-add, not a disqualifier — the structural dependence scores, not
  execution quality. Draw primarily from the "Product-engagement" evidence, where available.

- a2_score — OPERATIONAL STRAIN (process breaking under growth). COUNTERINTUITIVE BUT INTENDED:
  strain is the opportunity, so MORE strain scores HIGHER, and a smoothly-scaling, well-run
  company scores LOWER here. This is NOT "does cross-domain complexity exist" — every
  competitive company is complex, so complexity does not discriminate and must NOT drive this
  score. Score the EVIDENCE OF STRAIN broadly and in its own right — do NOT simply mirror the
  reset/restructuring event; a reorg is only ONE possible strain signal among many. Weight the
  STRUCTURAL strain signals most: headcount / scaling outrunning process; "first head of X"
  scramble hiring to fill capability gaps; breakage, backlogs, or quality / service problems
  under growth; visible scaling pains — and, as one signal among these, layoffs or reorgs
  framed as "grew too fast." Count REPORTED strain (employee / press accounts) only where the
  search found multiple independent sources — it already applied that bar. INTENDED BEHAVIOR: a
  healthy, smoothly-scaling, well-run company scores LOW (Weak/Absent) on A2 — the ABSENCE of
  strain correctly lowers fit, because there is no whitespace to own; a "better-run" company can
  legitimately score lower here than a struggling one, and that is correct. Draw primarily from
  the "Operational strain — structural" and "Operational strain — reported" evidence, where
  available.
    - Strong: clear, significant strain (typically structural + corroborated reported signals).
    - Absent: no operational strain found — the company is scaling smoothly.

- a3_score — DIGITAL CONSUMER HABITUAL-ENGAGEMENT PRODUCT. A digital consumer product where
  HABIT / RETENTION is LOAD-BEARING for the product's success. Score LOW for a consumer SURFACE
  without habit-dependence (a one-time transaction), or B2B2C where the real customer is the
  employer/payer and habit is secondary. Draws from the same "Product-engagement" evidence as
  A1, where available.

NULL vs 0 — read carefully; the system depends on this distinction:
- Emit null for an attribute ONLY when the evidence does not let you assess it at all.
  null means "couldn't assess — no/insufficient evidence."
- Emit 0 (Absent band) when you CAN assess the attribute and it is genuinely not characteristic
  of the company. 0 means "assessed, and it is absent."
- null is for missing EVIDENCE, not for a hard judgment call: if there IS evidence but the call
  is difficult, SCORE it and explain the difficulty in the basis — do not reach for null. null
  is the honest output ONLY when evidence is genuinely absent.
- Do NOT default to 0, and do NOT pick a low score, when you actually mean "unknown" — that
  silently corrupts the score.
- The system SUPPRESSES the overall capability score and flags the row for review whenever any
  attribute is null (it will NOT average over a gap), so emitting null has a real, safe effect:
  it routes the company to human review instead of producing a fabricated number.
- a1_basis / a2_basis / a3_basis: one line citing the specific evidence used — or, when the
  score is null, one line stating what evidence was missing.

Scale signal classification rules (institutional + outcomes):

institutional_distribution_signal:
- Use "strong" only when there is credible payer, employer, provider, benefits, health-system, pharma, government, or B2B2C distribution with named customers, covered lives, utilization, revenue, repeated channel evidence, or clear scaled adoption.
- Use "moderate" when there are pilots, partner pages, employer/provider positioning, limited named partnerships, or channel experiments without proof of scale.
- Use "weak" when institutional mentions exist but do not appear to drive adoption, revenue, or durable distribution.
- Use "none" when no meaningful institutional channel is visible.

outcomes_signal:
- Use "strong" when there is credible peer-reviewed, clinical, real-world, utilization, behavior-change, or health-improvement evidence tied to the company/product.
- Use "moderate" when evidence is company-reported, small-sample, indirect, engagement-only, validation-only, retrospective, or not clearly outcome-linked.
- Use "weak" when evidence is mostly marketing claims, testimonials, or indirect product claims.
- Use "none" when no meaningful outcomes/product-value evidence is found.

plausible_near_term_scale_path:
- Use true only when the company has a credible path to near-term scale through either commercial traction, institutional distribution, or strong outcomes plus a believable commercial/institutional channel.
- Use false when the company is interesting but public evidence does not show a clear path from product value to scalable adoption/revenue.

Native priority model:
- P0: Highest-priority target
  Use only for the clearest active-pursuit companies. Requires very strong thesis fit, strong PMF/scale, strong role fit, strong operator timing, and either multiple independently strong scale/value signals OR one exceptional scale engine with strong supporting evidence. P0 should be rare.
- P1: High-priority diligence
  Use only for companies that are meaningfully stronger than ordinary P2s and close to active pursuit, but not clean enough for P0. P1 still requires strong thesis fit, strong PMF/scale, strong role fit, credible operator timing, and no major timing blocker. Do not use P1 for companies that are public, too late, low-agency, or mainly interesting as market comparables.
- P2: Worth deeper diligence
  Use when the company clears the P2 priority gate but still has evidence gaps, timing ambiguity, role-fit questions, missing internal metrics, or one major missing pillar.
- P3: Watch list
  Use when the company has some fit or interesting signals, but does not clear the P2 priority gate because scale, evidence, role fit, or timing is not strong enough yet.
- P4: Low priority / likely reject
  Use when the company does not currently fit the thesis, has weak scale path, weak role fit, poor timing, or no compelling evidence of relevance.

Hard priority gates:
- P0 requires thesis_fit_score >= 85, pmf_scale_score >= 80, katelynd_role_fit_score >= 80, operator_timing_score >= 75, evidence_confidence_score >= 60, and stage_timing_fit must not be "too late". P0 should be rare.
- P1 requires thesis_fit_score >= 80, pmf_scale_score >= 75, katelynd_role_fit_score >= 75, operator_timing_score >= 65, evidence_confidence_score >= 55, and stage_timing_fit must not be "too late".
- If company_maturity_read is "public", maximum priority is P2 unless the role is explicitly a rare high-agency transformation role.
- If stage_timing_fit is "too late", maximum priority is P2.
- If likely_agency_level is "low", maximum priority is P2.
- Do not use P0 or P1 just because the company is strong. Priority is about Katelynd fit, role agency, timing, and evidence quality together.

Priority gate:
- P2 requires at least one real reason to believe the company has scale or near-term scale potential.
- P2 should usually require one of:
  1. pmf_scale_score >= 70 with evidence_confidence_score >= 50;
  2. commercial_scale_signal = "strong" with evidence_confidence_score >= 50;
  3. institutional_distribution_signal = "strong" with evidence_confidence_score >= 50;
  4. outcomes_signal = "strong" AND plausible_near_term_scale_path = true AND evidence_confidence_score >= 55.
- P1 should require the P2 gate PLUS strong thesis fit, role fit, and timing, with at least one strong scale engine or a strong outcomes-plus-scale path. P1 is not just a better P2; it is a near-active target.
- P0 should require P1-level fit PLUS a cleaner active-pursuit case: high PMF/scale, sufficient evidence confidence, and multiple strong scale/value signals or one exceptional scale engine.
- Strong Katelynd role fit should not override weak PMF/scale evidence.
- If pmf_scale_score is below 70 and both commercial traction and institutional distribution are weak/none, default to P3 even if thesis_fit_score or katelynd_role_fit_score is high.
- If evidence_confidence_score is below 50 and pmf_scale_score is below 70, default to P3 unless there is a very clear reason to keep P2.
- For D2C/cash-pay companies, P2 requires credible commercial-scale evidence or unusually strong outcomes evidence with a plausible commercial path.
- Pricing alone, a membership model, waitlist, app usage, funding, or role-fit relevance is not enough for P2.

Revenue quality / commercial traction examples:
- company-reported ARR/revenue/run-rate
- credible third-party estimated revenue/run-rate, such as Sacra or other private-market intelligence
- paid members/subscribers/customers
- renewal rate / retention / churn
- repeat purchase or repeat usage
- pricing power
- scalable margin structure
- CAC efficiency or organic demand
- implied annualized revenue from customer count x pricing, if direct ARR is unavailable

Institutional distribution examples:
- payer coverage or contracts
- employer benefits distribution
- provider or health-system adoption
- benefits platform distribution
- pharma/life sciences partnerships
- government/CMS/Medicare/Medicaid activity
- covered lives, named customers, utilization, or channel-driven revenue

Outcomes / product-value examples:
- peer-reviewed outcomes
- real-world evidence
- clinical trial evidence
- engagement/retention data tied to value
- behavior-change data
- utilization data
- patient/user improvement metrics

Scoring definitions:
1. thesis_fit_score
   Measures strategic alignment with Katelynd's thesis: health tech, meaningful outcomes, recurring engagement, data-rich product, credible scale path, and likely need for operator/product leadership.

2. pmf_scale_score
   Measures whether the company has credible product-market fit and scale potential.
   Use the scale-engine logic above. Strong commercial traction OR strong institutional distribution can each independently support a meaningful PMF/scale score.
   Do not punish private companies simply because internal metrics like churn, CAC, renewal, gross margin, or cohort retention are not public. Treat those as diligence gaps and evidence-confidence caveats.

3. evidence_confidence_score
   Measures how much to trust the public evidence.
   Estimated revenue from sources such as Sacra can support PMF/scale, but should usually keep evidence confidence moderate unless corroborated by company-reported data or multiple credible sources.

4. katelynd_role_fit_score
   Measures whether the company's likely operating problems match Katelynd's specific spike: scaling consumer/patient-facing products through product strategy, operating model design, data-informed decision-making, lifecycle/engagement systems, cross-functional execution, and product-ops/GM leadership.

   This is not a generic "could Katelynd add value?" score. A mature company can have relevant problems but still be a poor Katelynd role fit if the likely roles are narrow, highly specialized, or already owned by mature executive layers.

   High scores require evidence of at least two of:
   - consumer/patient behavior, engagement, retention, or lifecycle loops matter;
   - product, operations, analytics, clinical, payer, or commercial functions need stronger connection;
   - the company is scaling from early traction into repeatable execution;
   - the business likely needs a senior operator to build systems, cadence, prioritization, and accountability;
   - a VP Product, VP Ops, GM, Chief of Staff to CEO/COO, Product Ops, or Commercial/Product Strategy leader could own meaningful outcomes.

   Lower scores apply when the company is mostly clinical services, enterprise sales, infrastructure, provider workflow, reimbursement, or narrow functional execution where Katelynd's consumer product/operator background is less central.

5. operator_timing_score
   Measures whether this is the right maturity window for Katelynd to enter with high agency.

   Katelynd's preferred timing is post-PMF but pre-professionalized scale: typically Series A/B or early Series C, with clear early traction and emerging complexity, but before the company has fully built out mature executive layers and operating systems.

   High scores require evidence that the company likely needs to build or rebuild the operating system needed to scale toward $100M ARR.

   Do not score timing highly just because the company is successful, well-funded, high-growth, famous, or high-revenue. Very mature companies may be excellent businesses but poor timing fits if Katelynd would likely enter a narrow lane with limited agency.

   Timing caps:
   - Series A/B or equivalent early growth: can score 80-95 if PMF signs and operating complexity are present.
   - Early Series C / scale-up with major operating ambiguity: can score 70-90.
   - Late Series C/D or $75M-$150M ARR: cap at 70 unless there is clear evidence of a new business line, major operating rebuild, or unusually high-agency role need.
   - Series D+ / $100M+ ARR / heavily professionalized org: cap at 60 unless the company is still operationally immature or entering a major new scaling phase.
   - Public company or post-IPO: cap at 50 unless evaluating a specific role with an unusually broad mandate.

   For mature companies, explicitly distinguish:
   - "strong company, weak timing";
   - "strong company, role-scope dependent";
   - "still early enough for high-agency operator impact."

Calibration rules:
- If a company has strong commercial traction but weak payer/institutional distribution, do not automatically downgrade PMF/scale. Instead, note that the scale path is commercial/D2C rather than institutional.
- If a company has strong payer/employer/provider distribution but weak D2C revenue, do not automatically downgrade PMF/scale. Instead, note that the scale path is institutional.
- If both commercial traction and institutional distribution are weak, PMF/scale should be low unless outcomes/product-value evidence is exceptional and there is a plausible near-term scale path.
- If PMF/scale is high but evidence confidence is low, flag it.
- If a company receives P2 despite moderate evidence or PMF, explain the caveat.
- If a company receives P1, clearly explain why it is differentiated from ordinary P2s but not clean enough for P0.
- If a company receives P0, clearly explain the active-pursuit rationale.
- Strong Katelynd role fit should not override weak PMF/scale evidence.
- A company should not receive P2 solely because Katelynd could add value there or because the company is thesis-relevant.
- Do NOT flag possible P0/P1 under-promotion for a company whose main strength is a single estimated commercial scale signal if outcomes evidence, institutional distribution, and direct company-reported revenue/retention evidence are still weak or missing. In that case, use a P2 diligence caveat instead.

Return ONLY valid JSON. No markdown. No commentary outside JSON.

Controlled taxonomy instructions:
{taxonomy_prompt_block}

Important taxonomy rule:
- Return exactly one primary_market_segment code.
- Do not put distribution model, wearable/device modality, CGM, D2C, or virtual care into the primary market segment.
- Use subsegment_tags, product_model_tags, distribution_model_tags, and data_input_tags for nuance.
- If two primary segments seem plausible, choose the broader mutually exclusive umbrella segment from the taxonomy.

Use this JSON schema exactly:

{{
  "company": "{company_name}",
  "verified_facts_with_sources": [
    "fact with source/date",
    "fact with source/date"
  ],
  "inferences": [
    "clearly labeled inference",
    "clearly labeled inference"
  ],
  "unverified_or_weak_claims": [
    "claim or gap"
  ],
  "business_model_classification": "short classification",
  "taxonomy_classification": {{
    "primary_market_segment": "ONE approved primary market segment code from the controlled taxonomy. Do not invent new codes.",
    "subsegment_tags": ["zero or more approved subsegment tag codes from the controlled taxonomy"],
    "product_model_tags": ["zero or more approved product model codes from the controlled taxonomy"],
    "distribution_model_tags": ["zero or more approved distribution model codes from the controlled taxonomy"],
    "data_input_tags": ["zero or more approved data/input layer codes from the controlled taxonomy"],
    "classification_rationale": "short explanation of why the company belongs in the selected primary segment and how nuance was handled"
  }},
  "commercial_scale_assessment": "plain-English assessment of revenue quality, paid-customer scale, retention, pricing power, CAC/margin if available, and whether revenue is reported, estimated, or inferred",
  "pmf_scale_assessment": "plain-English assessment explaining the strongest scale engine, secondary scale engine if any, outcomes/product-value support, and key caveats",
  "maturity_evidence": {{
    "funding_rounds": [
      {{
        "type": "pre-seed / seed / series-a / series-b / series-c / series-d / series-e / ... / bridge / extension / SAFE / convertible / debt",
        "date": "YYYY or YYYY-MM, or 'unknown' if you cannot establish it",
        "amount": "$ amount, or 'unknown'",
        "is_priced_equity": "true for a priced equity round (seed/series-*); false for bridge/extension/SAFE/convertible/debt"
      }}
    ],
    "ipo_event": {{ "occurred": "true or false", "date": "YYYY or YYYY-MM, or 'unknown'" }},
    "ipo_status": "private / filed / public",
    "ipo_or_filing_date": "date if filed or public, else empty",
    "founding_year": "YYYY, or empty",
    "last_raise_date": "date of most recent raise, or empty",
    "last_raise_amount": "amount + currency of most recent raise, or empty",
    "total_funding": "total disclosed funding, or empty",
    "funding_stage_evidence": "short source/basis (name + date) for the funding rounds and ipo_status"
  }},
  "role_timing_assessment": {{
    "likely_agency_level": "high / medium / low / role-dependent",
    "stage_timing_fit": "ideal / good / borderline / too late / unclear",
    "why_now_or_why_not": "short explanation of whether Katelynd can enter with high agency now",
    "timing_penalty_applied": true
  }},
  "reset_evidence": {{
    "reset_events": [
      {{
        "event_type": "leadership-change / declared-transformation / founder-transition / post-failure-rebuild / restructuring-layoffs / strategic-pivot / ma-integration / ipo-prep",
        "basis": "source + date for THIS event",
        "creates_high_agency_opening": "yes / no / unclear"
      }}
    ]
  }},
  "commercial_evidence": {{
    "revenue_or_arr": "List ALL revenue/ARR/run-rate figures found, each with source, date, and type (company-reported / credible-estimate / implied-from-pricing / weak-single-source). Empty ONLY if NO real figure was found in any pass.",
    "paying_customer_count": "PAYING users/subscribers/members/customers only (exclude free/trial/pilot/waitlist) + source, or empty",
    "sponsored_user_scale": "NON-PAYING user-scale only -- total/registered/active users, MAU, app downloads/installs that are NOT paid -- with source/date and trend if available. e.g. '~2M registered users (2024), up from ~800k (2023)'. SECONDARY signal: NOT revenue, NOT paying customers; NEVER counts as revenue presence and NEVER feeds growth_signal OR growth_score. Empty if none.",
    "revenue_per_user": "company-stated, OR DERIVED from revenue ÷ paying-customer count or annual pricing WITH the inputs shown (mark DERIVED, not company-reported); empty only if neither a figure nor the inputs to derive one exist",
    "growth_signal": "growing / flat / declining, PLUS the quantified rate when found — carried WITH its period, and if COMPUTED from dated endpoints, WITH its inputs and a DERIVED tag. e.g. 'growing; 287% in 2023 (company-reported)' or 'growing; ~2.5x over ~9mo, DERIVED from $60M (Dec 2024) -> $150M (Sep 2025)'. NEVER strip the inputs/period or emit a bare rate. A DERIVED rate (or a third-party estimate) is a moderate-confidence source, NOT company-reported. Direction alone (no rate) is acceptable.",
    "business_model_type": "consumer-subscription / enterprise / payer-reimbursed / other",
    "funding_evidence": "raises / valuation (context ONLY; the system EXCLUDES this from the commercial signal)",
    "q1_acquisition": "is the PAYING base growing, flat, or declining? growing / flat / declining",
    "q2_monetization": "is revenue-per-user strong, typical, or weak FOR THIS BUSINESS MODEL? strong / typical / weak",
    "q3_funding_dependent": "does the commercial story rest mainly on funding/valuation rather than revenue/paying customers? yes / no",
    "q4_evidence_quality": "company-reported / credible-estimate / unverified-promotional"
  }},
  "capability_evidence": {{
    "a1_score": "0-100 within the bands (product-engagement structure) — or null if not assessable",
    "a1_basis": "one line citing the evidence used (or what was missing, if null)",
    "a2_score": "0-100 within the bands (operational STRAIN: HIGH = strained / high opportunity, LOW = smoothly-scaling) — or null if not assessable",
    "a2_basis": "one line citing the evidence used (or what was missing, if null)",
    "a3_score": "0-100 within the bands (digital consumer habit-product) — or null if not assessable",
    "a3_basis": "one line citing the evidence used (or what was missing, if null)"
  }},
  "scale_signal_assessment": {{
    "institutional_distribution_signal": "strong / moderate / weak / none",
    "institutional_distribution_signal_reason": "short reason",
    "outcomes_signal": "strong / moderate / weak / none",
    "outcomes_signal_reason": "short reason",
    "strong_scale_engine_present": true,
    "scale_engine_type": "commercial / institutional / both / outcomes_plus_scale_path / none",
    "plausible_near_term_scale_path": true,
    "priority_gate_preliminary_result": "qualifies_for_p0 / qualifies_for_p1 / qualifies_for_p2 / does_not_qualify_for_p2",
    "priority_gate_reason": "short explanation"
  }},
  "scores": {{
    "thesis_fit_score": {{
      "score": 0,
      "rationale": "why"
    }},
    "pmf_scale_score": {{
      "score": 0,
      "rationale": "why, explicitly referencing strongest scale engine logic"
    }},
    "evidence_confidence_score": {{
      "score": 0,
      "rationale": "why"
    }},
    "katelynd_role_fit_score": {{
      "score": 0,
      "rationale": "why"
    }},
    "operator_timing_score": {{
      "score": 0,
      "rationale": "why"
    }}
  }},
  "final_recommendation": "Strong fit, active pursuit / Strong fit, near-priority diligence / Possible fit, pending diligence / Watch list / Weak fit",
  "priority_level": "P0: Highest-priority target / P1: High-priority diligence / P2: Worth deeper diligence / P3: Watch list / P4: Low priority / likely reject",
  "calibration_flag": "short flag if needed, otherwise blank string",
  "entity_review_needed": "none / possible-alias -- set 'possible-alias' when carrying an entity-uncertain figure per the entity-doubt rule, else 'none'",
  "final_takeaway": "1-3 sentence concise conclusion"
}}
"""


def run_company_fit_brief(
    company_name,
    latest_status_findings,
    *,
    client,
    model: str = DEFAULT_MODEL,
    taxonomy_dir=None,
    taxonomy_prompt_block: str | None = None,
) -> str:
    """Run the company fit-brief synthesis (faithful port of notebook STEP 5).

    Loads the taxonomy block (unless one is supplied), builds the prompt via
    ``build_fit_brief_prompt``, and calls the model with web search OFF and
    ``max_output_tokens=6500`` — exactly as the notebook did. Returns the raw
    model text (expected to be JSON); parsing happens downstream, unchanged.
    """
    if taxonomy_prompt_block is None:
        taxonomy_prompt_block = load_taxonomy_prompt_block_for_fit_brief(taxonomy_dir)

    prompt = build_fit_brief_prompt(
        company_name, latest_status_findings, taxonomy_prompt_block
    )

    return call_openai(
        prompt,
        client=client,
        model=model,
        use_web_search=False,
        max_output_tokens=6500,
    )


# =============================================================================
# Business-model classifier (§B2) — Commit 1.
# The LLM extracts who_uses / who_pays (Rule 7); the deterministic mapper in
# structured_evidence.business_model_for emits the label. Prompt = SOT §B2 v1.13
# (the gate-B-validated EVIDENCE-ONLY + FREE-TO-CONSUMER wording, 2026-06-30).
# Pure builder so the prompt is asserted in tests without an API key.
# =============================================================================

BUSINESS_MODEL_PROMPT_TEMPLATE = """You classify a HEALTH company on TWO INDEPENDENT axes so a downstream deterministic mapper can label it B2B / B2B2C / B2C. You do NOT emit the label -- you emit ONLY the two axis reads, their bases, and a confidence. (A separate locked mapper turns these into the label; a human-locked floor overrides you for a few known cases. Your only job is an honest, evidence-grounded read of the two axes.)

Output ONE JSON object and nothing else:
{{"who_uses": "consumer" or "professional",
  "who_uses_basis": "<one line: who actually operates/interacts with THIS company's OWN product/service>",
  "who_pays": "consumer" or "institution" or "mixed",
  "who_pays_basis": "<one line: who MATERIALLY pays for that use>",
  "who_uses_confidence": "high" or "low"}}

AXIS 1 -- who_uses. The ONLY question: who is the END-USER of THIS company's OWN product/service?
- "consumer" = a regular person (patient / member / individual) personally interacts with the company's own product or service -- even when a clinician or coach is part of the service, and even when an institution pays. Care delivered THROUGH the company's own employed clinicians/coaches to a person is STILL consumer use (the person is the end-user of the company's service).
- "professional" = the product is operated BEHIND THE SCENES by a professional (clinician, hospital/care-team staff, developer) as a tool / infrastructure / enablement layer / data product; the consumer never personally uses THIS company's product. Provider-facing tools, hospital-at-home enablement platforms, clinical-evidence/data products, and back-office APIs are "professional".
- FREQUENCY FIREWALL: usage frequency is IRRELEVANT to who_uses. A clinician using a professional tool every day is STILL "professional"; a patient using a consumer app only occasionally is STILL "consumer". Do NOT let high professional-usage frequency pull a professional tool into "consumer".
- If you genuinely cannot tell whether the consumer is the end-user or the product runs behind the scenes, set who_uses_confidence = "low".

AXIS 2 -- who_pays. The question: who MATERIALLY pays for the consumer's use?
- "consumer" = the individual pays out of pocket / cash-pay / a consumer subscription is the PRIMARY, material revenue path (even if a tiny employer or pilot channel also exists).
- "institution" = an employer, health plan, payer, health system, government, or pharma/sponsor materially pays; the consumer receives it free or heavily subsidized.
- "mixed" = BOTH a real consumer-pay path AND a real institutional-pay path are MATERIAL and established (not a single mention).
- MATERIALITY BAR (do NOT over-read a minor proof-point): a SINGLE employer page, one pilot, one "ask your employer" mention, or one small partnership does NOT make who_pays "mixed" or "institution". Require a MATERIAL, established institutional payment channel -- named payers / covered lives / a scaled employer book / a health-system JV -- before moving off "consumer". When the consumer cash-pay path is clearly primary and the institutional path is a single minor proof-point, answer "consumer".
- EVIDENCE-ONLY (do NOT use outside knowledge): base who_pays ONLY on payment channels MATERIALLY ESTABLISHED IN THE EVIDENCE BELOW. Do NOT infer an institutional channel from general or background knowledge about the company. If the Evidence does not materially establish an institutional payment channel, the consumer cash-pay path governs -> "consumer" -- even if you believe the company has institutional deals elsewhere.
- FREE-TO-CONSUMER: a product that is FREE to the individual has NO consumer-pay path. If the consumer pays nothing and an institution (pharma / sponsor / employer / payer) materially pays, answer "institution", not "mixed". "mixed" requires BOTH a real consumer-PAYMENT path AND a real institutional one.

Company: {company}
Evidence:
{evidence}"""


def build_business_model_prompt(company_name, evidence) -> str:
    """Build the §B2 who_uses / who_pays classifier prompt (gate-B-validated wording, SOT v1.13).

    Pure function: no LLM call, no I/O. The LLM emits ONLY the two axis reads + bases + confidence;
    the deterministic label comes from ``structured_evidence.business_model_for``.
    """
    return BUSINESS_MODEL_PROMPT_TEMPLATE.format(company=company_name, evidence=evidence)


def run_company_business_model(
    company_name,
    evidence,
    *,
    client,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 300,
):
    """Run the §B2 classifier extraction for one company: build the prompt, call the model with
    web search OFF, return the raw model text (expected to be one JSON object). Parsing + the
    deterministic mapper run downstream (``structured_evidence.flatten_business_model_fields`` /
    ``business_model_for``). The classifier reads STORED evidence (Rule 7) — no web search."""
    prompt = build_business_model_prompt(company_name, evidence)
    return call_openai(
        prompt,
        client=client,
        model=model,
        use_web_search=False,
        max_output_tokens=max_output_tokens,
    )


# =============================================================================
# Background-fit gradient (§B5) — Commit 4.
# The LOCKED §B5 v1.7 prompt (validated 2026-06-29; byte-faithful to the SOT and the spike). A GRADIENT
# 1-10, NOT a gate; errors are recoverable (re-runnable per company). Precondition: who_uses == consumer
# (every gate-passed company meets it — professional was floored at PATH Test A). Emits background_fit
# (int 1-10) + data_feedback_loop ("yes"/"no"). The frozen BG_FIT dict (spike bg_fit_scores.py) is the
# VALIDATION REFERENCE — the hardened step RE-RUNS this prompt and should reproduce it within tolerance;
# the frozen scores are NOT wired in as the scorer's output.
# =============================================================================

BACKGROUND_FIT_PROMPT_TEMPLATE = """You score BACKGROUND FIT for a CONSUMER-facing health company: HOW CLOSE its consumer-engagement model is to the "mobile-games loop" -- habitual, high-frequency, retention-driven engagement the consumer keeps returning to on their own. This is a GRADIENT (1-10), not a pass/fail. (Precondition already met upstream: the consumer is the end-user of the company's OWN product/service.)

Output ONE JSON object and nothing else:
{{"background_fit": <integer 1-10>,
  "data_feedback_loop": "yes" or "no",
  "basis": "<one line describing the consumer's ACTUAL ongoing engagement>"}}

SCALE:
- 9-10 = a tight DATA-FEEDBACK LOOP: the consumer sees their OWN body/health data -> acts on it -> sees the result reflected back -> repeats. The habitual self-tracking loop (metabolic / CGM / wearable / biomarker / continuous activity or glucose tracking). This loop is the top-of-scale AMPLIFIER -> set data_feedback_loop = "yes".
- 6-8 = a STRONG consumer-habit model WITHOUT that tight data-loop: frequent, retention-driven engagement the consumer actively sustains (recurring coaching / therapy / care they personally show up for, a consumer app with real habitual use, an ongoing condition-management relationship). A strong consumer-health company that simply LACKS the data-feedback loop STILL SCORES SOLIDLY HERE -- do NOT floor it merely for lacking the loop.
- 3-5 = a genuinely EPISODIC / intermittent consumer relationship: the consumer engages around a discrete need or event and then largely leaves, with little sustained habit.
- 1-2 = almost no recurring consumer-engagement surface.

DO NOT under-score (the "periodic" trap): judge the consumer's ACTUAL ongoing engagement with the company's OWN product/service. Care delivered through the company's employed clinicians/coaches, or paid for by an employer/health-plan, is STILL the consumer's own habit -- do not label it "periodic" for that reason. A serious or medically-driven condition is NOT automatically low-frequency: a daily nutrition program, an ongoing therapy relationship, or continuous condition management is HABITUAL even when the underlying need is medical. Score 3-5 ONLY when the engagement is genuinely one-off / intermittent.

Company: {company}
Evidence:
{evidence}"""


def build_background_fit_prompt(company_name, evidence) -> str:
    """Build the §B5 v1.7 LOCKED background-fit gradient prompt (validated wording). Pure function:
    no LLM call, no I/O. Emits background_fit (1-10) + data_feedback_loop + basis; the deterministic
    persistence is ``structured_evidence.flatten_background_fit_fields``."""
    return BACKGROUND_FIT_PROMPT_TEMPLATE.format(company=company_name, evidence=evidence)


def run_company_background_fit(
    company_name,
    evidence,
    *,
    client,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 220,
):
    """Run the §B5 background-fit gradient for one company: build the locked prompt, call the model with
    web search OFF, return the raw model text (expected to be one JSON object). The caller enforces the
    who_uses == consumer precondition (``structured_evidence.background_fit_applies``) and parses via
    ``flatten_background_fit_fields``. Reads STORED evidence (Rule 7) — no web search."""
    prompt = build_background_fit_prompt(company_name, evidence)
    return call_openai(
        prompt,
        client=client,
        model=model,
        use_web_search=False,
        max_output_tokens=max_output_tokens,
    )


# =============================================================================
# Growth extractor (§B6 v1.24 — BAND CLASSIFICATION). The last LLM-facing growth prompt.
# The extractor now CLASSIFIES a company's revenue growth into ONE of four bands (high/solid/slow/unknown),
# given the STAGE's Scale-B cutpoints — it does NOT report figures and NEVER derives a rate (the v1.23
# report-figures / same-source derive machinery is SUPERSEDED + REMOVED). The deterministic scorer
# (structured_evidence.score_growth) maps the band -> a fixed score. The §B6.1 fence (revenue/$ only; counts
# are SCALE) is preserved. Pure builder so it is asserted in tests without an API key.
# =============================================================================

GROWTH_BAND_EXTRACTOR_PROMPT_TEMPLATE = """You classify a health company's REVENUE-GROWTH into ONE band, for a downstream stage-relative growth score. Read the evidence and emit ONE growth read. You CLASSIFY into a band; you do NOT compute a precise rate.

Output ONE JSON object and nothing else:
{{"growth_band": "high" | "solid" | "slow" | "unknown",
  "growth_basis": "revenue-rate" | "revenue-trajectory" | "counts-scale" | "none",
  "source_mode": "single-source" | "complementary-multi" | "conflict" | "none",
  "evidence": "<one line: the figures + their sources + the trajectory you banded on; write 'declining' if revenue is shrinking>"}}

THE BANDS -- phase-relative; the cutoffs below are for THIS company's stage ({stage}):
- "high"  -- fast-growing FOR ITS STAGE: revenue growth AT OR ABOVE {high_cut}% YoY, OR "tripled / 3x / Nx", OR a clearly-high revenue run-rate/trajectory for the stage.
- "solid" -- real, credible revenue growth: roughly {solid_lo}%-{high_cut}% YoY for this stage, or a clear multi-fold revenue trajectory that lands in this range.
- "slow"  -- modest / decelerating / DECLINING: below {solid_lo}% YoY for this stage, flat, or shrinking. (If revenue is shrinking, band "slow" AND write "declining" in evidence.)
- "unknown" -- NO credible REVENUE-growth signal. Do NOT guess; do NOT manufacture growth.

HOW TO BAND -- TRAJECTORY MAGNITUDE, not a precise rate:
- You read the ORDER OF MAGNITUDE of the revenue trajectory (grew ~Nx over ~M years) and pick the band -- you do NOT need an exact rate.
- A band MAY rest on: (a) a single-source stated rate; (b) a single-source revenue series (SAME source, 2+ dated points); OR (c) COMPLEMENTARY revenue points from DIFFERENT sources/years with NO competing estimate for the same period (e.g. $4.5M-2021 from one shop + $35M-2023 from another) -- read TOGETHER as a trajectory magnitude. Two independent shops both showing several-fold growth is MORE credible, not less -- do NOT refuse them.
- REFUSE only a genuine CONFLICT: two sources giving CONTRADICTORY figures for the SAME period. Then do not manufacture a number -> band on the most-credible single point, else "unknown". (Different years from different shops is NOT a conflict.)
- A launch-from-$0 revenue trajectory ($0 -> $N): band by how large $N is FOR THE STAGE (a big run-rate reached fast is "high").
- Set "source_mode": "single-source" | "complementary-multi" (different years/sources, no same-period conflict) | "conflict" (contradictory same-period) | "none" (no revenue figures).

REVENUE / $ ONLY -- the FENCE (HARD, the most important rule):
- A band may rest ONLY on REVENUE / ARR / $ growth. NON-revenue COUNTS -- covered lives, members, patients, users, downloads, MAU, headcount, partners -- are SCALE, NOT revenue. If the ONLY growth signal is a count/scale figure, the band is "unknown" and "growth_basis" is "counts-scale". NEVER band HIGH/SOLID on counts. ("Covered lives rose 50%" / "members grew 3x" / "patients grew 485%" is NOT revenue growth.)
- Set "growth_basis": "revenue-rate" (a stated %/multiple) | "revenue-trajectory" (dated revenue points read as magnitude) | "counts-scale" (only non-revenue counts -> band MUST be "unknown") | "none" (no growth signal at all).

Company: {company}
Evidence:
{evidence}"""


def _fmt_cut(pct) -> str:
    """Format a Scale-B cutpoint % for the prompt without a trailing '.0' (25.0 -> '25')."""
    return f"{float(pct):g}"


def build_growth_extractor_prompt(company_name, evidence, stage) -> str:
    """Build the §B6 v1.24 BAND growth-extractor prompt. Pure function: no LLM call, no I/O. The stage's
    Scale-B score-8 (HIGH cutpoint) and score-5 (SOLID floor) are injected so the LLM bands PHASE-RELATIVELY
    against the LOCKED Scale B (the same cutoffs `structured_evidence.band_for_rate` uses). The LLM emits a
    band + its evidence trail; the deterministic ``structured_evidence.score_growth`` maps band -> score."""
    gstage = se._growth_stage(stage)
    pts = se.GROWTH_SCALE[gstage]
    return GROWTH_BAND_EXTRACTOR_PROMPT_TEMPLATE.format(
        company=company_name, evidence=evidence, stage=gstage,
        high_cut=_fmt_cut(pts[7]), solid_lo=_fmt_cut(pts[4]))


def run_company_growth(
    company_name,
    evidence,
    *,
    stage,
    client,
    model: str = DEFAULT_MODEL,
    max_output_tokens: int = 200,
):
    """Run the §B6 v1.24 growth BAND classification for one company: build the stage-aware prompt, call the
    model with web search OFF, return the raw model text (expected to be one JSON band read). Parsing +
    scoring run downstream (``structured_evidence.flatten_growth_read`` / ``score_growth``). Reads STORED
    evidence (Rule 7)."""
    prompt = build_growth_extractor_prompt(company_name, evidence, stage)
    return call_openai(
        prompt,
        client=client,
        model=model,
        use_web_search=False,
        max_output_tokens=max_output_tokens,
    )


# =============================================================================
# STEP 7 - Batch runner loop (per-company checkpointing + error recovery)
# =============================================================================


@dataclass
class ResearchBatchResult:
    """Outcome of a research batch run.

    ``completed`` / ``reused`` / ``failed`` partition the *requested* companies:

    * ``completed`` — researched successfully in THIS run (now in the checkpoint).
    * ``reused`` — skipped because already complete in the checkpoint (resume).
    * ``failed`` — raised this run (API/network/bad JSON); NOT checkpointed, so
      they are retried on the next resume.

    The durable artifact is the checkpoint CSV at ``checkpoint_path``.
    """

    completed: list = field(default_factory=list)
    reused: list = field(default_factory=list)
    failed: dict = field(default_factory=dict)
    checkpoint_path: str = ""


def _company_and_query(company_item):
    """Faithful to STEP 7: an item is either ``{"company", "research_query"}`` or a bare string."""
    if isinstance(company_item, dict):
        return company_item["company"], company_item["research_query"]
    return company_item, company_item


def _is_nonblank(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def _row_is_complete(row) -> bool:
    """A checkpoint row is complete iff all nine research columns are non-blank AND none is
    a ``SEARCH_FAILED`` marker. A marker is a FAILED search (evidence unavailable), not a
    real finding — treating it as complete would bake the hole in and skip the company on
    resume; treating it as incomplete re-researches it (visible AND auto-retried)."""
    values = [row.get(col, "") for col in REQUIRED_RESEARCH_COLUMNS]
    if any(is_search_failure(v) for v in values):
        return False
    return all(_is_nonblank(v) for v in values)


def _build_latest_status_findings(
    funding, payer, outcomes, commercial, growth, paying, org_events, operating_characteristics
) -> str:
    """Assemble the research findings into the synthesis input.

    The four original STEP 7 sections, the growth-rate recovery union (growth-directed
    N=5; synthesis derives growth_signal from its dated endpoints) and the paying-count
    recovery union (paying-directed N=5; synthesis derives paying_customer_count from it),
    plus the two Slice 3.7 operator sections (org events -> reset; operating
    characteristics -> capability-fit, scored in Slice 4).
    """
    return f"""
Funding:
{funding}

Payer / institutional signal:
{payer}

Outcomes:
{outcomes}

Commercial scale / revenue quality:
{commercial}

Revenue growth / dated revenue endpoints:
{growth}

Paying-customer count:
{paying}

Recent org / leadership events (last ~12-18 months):
{org_events}

Operating characteristics (product-engagement + operational strain):
{operating_characteristics}
"""


def run_research_batch(
    companies,
    *,
    client,
    checkpoint_path,
    model: str = DEFAULT_MODEL,
    mirror_checkpoint_path=None,
    taxonomy_dir=None,
    wait_between_searches: float = DEFAULT_WAIT_BETWEEN_SEARCHES,
    wait_between_passes: float = DEFAULT_WAIT_BETWEEN_PASSES,
    sleep_fn=time.sleep,
    validate_json: bool = True,
) -> ResearchBatchResult:
    """Run research + fit brief for each company, with per-company recovery.

    Faithful port of notebook STEP 7:

    * Resume: a checkpoint row with all ``REQUIRED_RESEARCH_COLUMNS`` non-blank is
      "complete"; those companies are skipped (``reused``) and not re-researched.
    * After each successful company the checkpoint is written atomically and
      (optionally) mirrored, so a runtime loss never loses completed work.
    * The web searches (the four original + the two Slice 3.7 operator searches:
      org events, operating characteristics) run with the faithful wait between them
      (injected ``sleep_fn``); the commercial/revenue search is now an N-pass
      ``search_with_recovery`` union with ``wait_between_passes`` between its passes.
      Then the fit brief is synthesized.

    New here (the missing per-company recovery): each company's work is wrapped so
    one failure — an API error, a network error, or (when ``validate_json``) a fit
    brief that does not parse — is caught, logged, recorded in ``failed``, and the
    loop continues to the next company. A failed company is NOT checkpointed, so it
    is retried on the next resume. ``KeyboardInterrupt`` / ``SystemExit`` are not
    ``Exception`` subclasses and propagate (re-raised explicitly for clarity).
    """
    checkpoint_path = Path(checkpoint_path)

    results: list = []
    completed_companies: set = set()

    # --- faithful resume: load already-complete rows from the checkpoint ---
    if checkpoint_path.exists():
        existing = load_csv(checkpoint_path)
        for col in REQUIRED_RESEARCH_COLUMNS:
            if col not in existing.columns:
                existing[col] = ""
        if not existing.empty:
            complete_rows = existing[existing.apply(_row_is_complete, axis=1)]
            complete_rows = complete_rows[REQUIRED_RESEARCH_COLUMNS].copy()
            results = complete_rows.to_dict("records")
            completed_companies = set(complete_rows["company"].astype(str).tolist())

    result = ResearchBatchResult(checkpoint_path=str(checkpoint_path))

    for company_item in companies:
        company, research_query = _company_and_query(company_item)

        if str(company) in completed_companies:
            logger.info("Skipping %s; already complete in checkpoint.", company)
            result.reused.append(company)
            continue

        try:
            # Funding-ROUNDS recovery (the 4th recovery field): source-directed retries for LATEST-round
            # RECALL (the Sword 2/4 miss) + an observability-only presence check. Built v1.2. The union ->
            # fit-brief synthesis (maturity_evidence.funding_rounds, c3779cc) -> the funding_stage mapper.
            funding, funding_recovery = search_with_recovery(
                search_funding,
                research_query,
                client=client,
                model=model,
                retry_prompt_builder=funding_rounds_source_directed_prompt,
                presence_check=funding_latest_round_presence_check,
                field_name="funding_stage",
                n_passes=FUNDING_RECOVERY_PASSES,
                wait_between_passes=wait_between_passes,
                sleep_fn=sleep_fn,
            )
            logger.info(
                "Funding-rounds recovery for %s: %s passes, recent_round_present=%s.",
                company,
                funding_recovery.n_passes,
                funding_recovery.figure_present,
            )
            sleep_fn(wait_between_searches)

            payer = search_payer_signal(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            outcomes = search_outcomes(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            commercial, commercial_recovery = search_with_recovery(
                search_commercial_scale,
                research_query,
                client=client,
                model=model,
                retry_prompt_builder=revenue_source_directed_prompt,
                presence_check=revenue_presence_check,
                field_name="revenue",
                n_passes=REVENUE_RECOVERY_PASSES,
                wait_between_passes=wait_between_passes,
                sleep_fn=sleep_fn,
            )
            logger.info(
                "Revenue recovery for %s: %s passes, figure_present=%s.",
                company,
                commercial_recovery.n_passes,
                commercial_recovery.figure_present,
            )
            sleep_fn(wait_between_searches)

            # Growth-rate recovery: its OWN per-field config (growth-directed retries +
            # presence check) at N=5 -- the synthesis derives growth_signal from this
            # union's dated endpoints. Built against FRAMEWORK_VERSION v1.1.
            growth, growth_recovery = search_with_recovery(
                search_commercial_scale,
                research_query,
                client=client,
                model=model,
                retry_prompt_builder=growth_rate_source_directed_prompt,
                presence_check=growth_rate_presence_check,
                field_name="growth_rate",
                n_passes=GROWTH_RECOVERY_PASSES,
                wait_between_passes=wait_between_passes,
                sleep_fn=sleep_fn,
            )
            logger.info(
                "Growth-rate recovery for %s: %s passes, figure_present=%s.",
                company,
                growth_recovery.n_passes,
                growth_recovery.figure_present,
            )
            sleep_fn(wait_between_searches)

            # Paying-customer-count recovery: its OWN per-field config (paying-directed retries +
            # presence check) at N=5 -- matches the re-measure (paying-directed, not the
            # revenue-directed commercial union). Built against FRAMEWORK_VERSION v1.2.
            paying, paying_recovery = search_with_recovery(
                search_commercial_scale,
                research_query,
                client=client,
                model=model,
                retry_prompt_builder=paying_count_source_directed_prompt,
                presence_check=paying_count_presence_check,
                field_name="paying_customer_count",
                n_passes=PAYING_RECOVERY_PASSES,
                wait_between_passes=wait_between_passes,
                sleep_fn=sleep_fn,
            )
            logger.info(
                "Paying-count recovery for %s: %s passes, figure_present=%s.",
                company,
                paying_recovery.n_passes,
                paying_recovery.figure_present,
            )
            sleep_fn(wait_between_searches)

            org_events = search_org_events(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            operating_characteristics = search_operating_characteristics(
                research_query, client=client, model=model
            )

            latest_status_findings = _build_latest_status_findings(
                funding, payer, outcomes, commercial, growth, paying, org_events, operating_characteristics
            )

            fit_brief = run_company_fit_brief(
                company,
                latest_status_findings,
                client=client,
                model=model,
                taxonomy_dir=taxonomy_dir,
            )

            if validate_json:
                # Reuse the package's existing parser; it RAISES on unparseable
                # output, which the per-company handler records as a failure.
                parse_first_json_object(fit_brief)

            new_record = {
                "company": company,
                "date_researched": datetime.now().strftime("%Y-%m-%d"),
                "funding_finding": funding,
                "payer_institutional_finding": payer,
                "outcomes_finding": outcomes,
                "commercial_scale_finding": commercial,
                "growth_finding": growth,
                "paying_finding": paying,
                "org_events_finding": org_events,
                "operating_characteristics_finding": operating_characteristics,
                "fit_brief_json": fit_brief,
            }

            results.append(new_record)
            completed_companies.add(str(company))
            result.completed.append(company)

            # Persist after each company (local + optional mirror), faithfully.
            df = (
                pd.DataFrame(results)
                .drop_duplicates(subset=["company"], keep="last")
                .reset_index(drop=True)
            )
            atomic_write_csv(checkpoint_path, df)
            if mirror_checkpoint_path is not None:
                copy_with_backup(checkpoint_path, mirror_checkpoint_path)

            logger.info("Checkpoint saved after %s.", company)
            sleep_fn(wait_between_searches)  # trailing wait between companies

        except (KeyboardInterrupt, SystemExit):
            # Not Exception subclasses; let an operator interrupt abort cleanly.
            raise
        except Exception as exc:  # noqa: BLE001 - per-company recovery is the point
            logger.warning(
                "Research failed for %s: %s: %s", company, type(exc).__name__, exc
            )
            result.failed[company] = f"{type(exc).__name__}: {exc}"
            continue

    return result


# =============================================================================
# HARDENED RESET RE-EMITTER (§B4 v1.16) — Commit 8 (Option B).
#
# The R1 checkpoint's reset_evidence was researched with the OLD pre-v1.5 emitter (liberal opening=yes on
# many leadership-change events), so a naive type+opening read over-fires. Option B fixes the DATA, not the
# deterministic engine: re-run the COMMITTED hardened v1.16 substance-classifier (the one validated 5/5 in
# Commit 3a — grow/foodsmart FIRE; sword/oura/noom EXCLUDE by substance) over each company's org_events, so
# the checkpoint carries correct classifications and `derive_reset_signal` stays clean (type + opening only,
# NO basis-regex shim). The substance wording below is the SAME block embedded in build_fit_brief_prompt (a
# sync test asserts byte-identity) — this is a standalone re-run of committed wording, not a fresh draft.
# =============================================================================

_RESET_SUBSTANCE_BLOCK = """Reset / restructure evidence — capture whether the company is in a moment of organizational disruption that creates a HIGH-AGENCY ENTRY OPENING for a senior operator (whitespace + a forward-looking mandate to BUILD) — NOT about strategy or health, and NOT a reward for any change that merely looks disruptive.
A company may be doing SEVERAL of these at once. List EACH distinct event as its own object in reset_events, answer the opening question PER EVENT on its own terms, and do NOT let one event's nature determine another's. If you find no reset/restructure events, return an empty list [].

CLASSIFY BY SUBSTANCE, NOT PRESS FRAMING. Judge each event on what ACTUALLY changed, never on the company's label for it. "Transformation," "evolution," "pivotal," "next chapter" are marketing words — they do not decide event_type. You are the single emitter: classify event_type and read the opening from the underlying facts, even when that means re-classifying how the source framed it. (The per-event reads in the "Recent org / leadership events" findings are inputs to weigh, not labels to transcribe.)

For each event:
- event_type — choose by SUBSTANCE:
  - leadership-change — a new CEO / senior exec brought in to BUILD or TURN AROUND the company (a reopened operating window). NOT a routine functional hire to staff ongoing growth (see the opening rule).
  - founder-transition — founder stepping back / bringing in professional leadership to scale.
  - post-failure-rebuild — rebuilding after a stumble, with a forward mandate.
  - restructuring-layoffs — restructuring / layoffs. EITHER a rebuild-toward-growth OR a contraction-toward-decline — do NOT prejudge it; the opening question for THIS event decides.
  - declared-transformation — an OPERATING-MODEL rebuild: rebuilding HOW the company runs INTERNALLY (its operating systems, org, processes). Reserve STRICTLY for an internal operating rebuild. A change to WHAT the company sells, its product line, its pricing, or its go-to-market is NOT this.
  - strategic-pivot — a change to the BUSINESS MODEL, PRODUCT STRATEGY, PRICING, or GO-TO-MARKET: e.g. D2C -> payer / B2B; a new product category or an "evolution" into a different kind of product; a pricing-model change (engagement-based -> outcome-based); expansion into a new clinical / product area. This is strategic-pivot EVEN IF framed as a "transformation," "evolution," or "pivotal" moment. ("Changed/added what we sell or how we price/sell it" = strategic-pivot; "rebuilding how we operate internally" = declared-transformation.)
  - ma-integration — merger / acquisition integration work.
  - ipo-prep — IPO preparation: an S-1 / draft (incl. confidential) registration statement, public-market-readiness, or "going public" activity. A MATURE-TRAJECTORY event, the OPPOSITE of a reopened build-window. Classify ALL IPO / S-1 / public-market-readiness events here, even when framed as a "transformation" or "next chapter."
- basis — cite the source + date for THIS event.
- creates_high_agency_opening — for THIS event, by HONEST confidence:
  - "yes" ONLY when THIS event CLEARLY reopens a high-agency window (the company is actively rebuilding / turning around and needs a senior operator to BUILD). Do NOT round up to "yes" when uncertain.
  - "no" when THIS event is a DEFENSIVE reaction (a pivot under pressure, a contraction toward survival/decline, routine integration) or a MATURE-trajectory event (ipo-prep).
  - "unclear" when the evidence doesn't let you tell.
  - EXEC ADD — read the opening by STRUCTURAL ROLE, not the company's growth framing: a senior exec ADDED to SUPPORT / DRIVE / SCALE an existing growth / expansion / partnerships / commercial motion (a CMO, CRO, or similar growth / commercial hire — "expanding the executive team" to fuel growth) -> "unclear". This is the common scaling-company case and is NOT a reopened build-window, EVEN when the title is senior. Emit "yes" for an exec add ONLY for a CLEAR structural reset — a NEW CEO replacing the prior CEO, a founder stepping back for professional leadership, OR a FIRST-EVER / NEWLY-CREATED C-suite seat that stands up a function the company did NOT previously have (e.g. its FIRST CFO building finance / operating discipline). The test: does this BUILD a missing operating function (-> "yes") or STAFF an existing growth thrust (-> "unclear")?
  - Example: a company that (a) shifts its model under pressure [strategic-pivot, opening=no] AND (b) restructures to fund a rebuild toward expansion [restructuring-layoffs, opening=yes] — list BOTH; the restructuring's "yes" stands on its own.
(The deterministic rule downstream fires ONLY when event_type is a firing type AND creates_high_agency_opening == "yes". strategic-pivot, ma-integration, and ipo-prep NEVER fire; "unclear" / "no" never fire; multiple "unclear" events do NOT sum to a fire. Your job is an honest per-event SUBSTANCE classification + an honest opening read — the deterministic code decides what fires.)"""


RESET_EMITTER_PROMPT_TEMPLATE = (
    "You classify a health company's recent org / leadership events into canonical reset_events.\n"
    + _RESET_SUBSTANCE_BLOCK
    + "\n\nOutput ONE JSON object and nothing else:\n"
    + '{{"reset_events": [{{"event_type": "...", "basis": "...", "creates_high_agency_opening": "yes / no / unclear"}}]}}\n'
    + "\nCompany: {company}\nRecent org / leadership events:\n{events}"
)


def build_reset_emitter_prompt(company_name, events) -> str:
    """Build the standalone §B4 v1.16 hardened reset-emitter prompt (the committed substance block, run on
    its own over org_events evidence). Pure function: no LLM call. The LLM emits reset_events; the
    deterministic ``structured_evidence.derive_reset_signal`` decides what fires."""
    return RESET_EMITTER_PROMPT_TEMPLATE.format(company=company_name, events=events)


def run_company_reset(company_name, events, *, client, model: str = DEFAULT_MODEL, max_output_tokens: int = 400):
    """Run the §B4 v1.16 hardened reset re-emission for one company: build the prompt, call the model with
    web search OFF, return the raw model text (one JSON object with a reset_events list). Reads STORED
    org_events evidence (Rule 7) — no web search."""
    return call_openai(
        build_reset_emitter_prompt(company_name, events),
        client=client,
        model=model,
        use_web_search=False,
        max_output_tokens=max_output_tokens,
    )


# =============================================================================
# R1 RE-VALIDATION ORCHESTRATION (§B7 v1.22 — CACHING / persisted reads) — Commit 8.
#
# The live driver behind the R1 re-validation. v1.22: take each company's four §B scoring reads (§B2
# classifier, §B4 hardened reset, §B6 growth, §B5 bg_fit) ONCE, PERSIST them in a cache, and score OFF the
# cache — reproducible BY CONSTRUCTION (a re-score reads the same frozen values → identical tiers; the N=5
# stability machinery is RETIRED, and temp-0/seed model determinism is not available on gpt-5.4-mini). All
# scoring/flattening/tally logic is committed, tested structured_evidence code; this layer does the ONE-TIME
# LLM reads + the verified parsing (byte-faithful to the signed cells 177/178/180) and the caching.
# =============================================================================


def _extract_json(text) -> dict:
    """Parse the first {...} object out of a raw model response (the signed cells' `out[find:{rfind}+1]`
    slice). Returns {} on absence / malformed — never a guessed value."""
    text = str(text or "")
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return {}
    try:
        parsed = json.loads(text[i:j + 1])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _r1_classifier_read(row, *, client, model):
    """Live §B2 read -> {who_uses, who_pays, who_uses_confidence} (flat JSON, per signed cell 180)."""
    d = _extract_json(run_company_business_model(
        row["company"], se.classifier_evidence(row), client=client, model=model))
    return {"who_uses": d.get("who_uses", ""), "who_pays": d.get("who_pays", ""),
            "who_uses_confidence": d.get("who_uses_confidence", "")}


def _r1_growth_read(row, *, client, model):
    """Live §B6 v1.24 BAND read -> flattened growth columns (growth_band + growth_evidence). Evidence =
    canonical_growth_evidence off the FLATTENED row (growth_signal + revenue_or_arr + growth_finding, §B6.1
    v1.18); the band prompt is STAGE-AWARE (the persisted funding_stage, with the DOCUMENTED_STAGE_OVERRIDE
    applied — same stage the scorer uses) so the LLM bands phase-relatively. The read is wrapped under
    `growth_read` for flatten_growth_read (the extractor emits the read at top level)."""
    flat = se.flatten_checkpoint_row(row)
    stage = se._norm_stage(flat.get("funding_stage"))
    key = se._norm_company(row.get("company"))
    if key in se.DOCUMENTED_STAGE_OVERRIDES:
        stage = se.DOCUMENTED_STAGE_OVERRIDES[key]
    d = _extract_json(run_company_growth(
        row["company"], se.canonical_growth_evidence(flat), stage=stage, client=client, model=model))
    return se.flatten_growth_read({"growth_read": d})


# §B5 v1.24 — bg_fit is the ONE genuinely noisy continuous read (grow wobbled 4<->8; a single cached sample
# froze it low). Take N reads at cache-population and cache the ROUNDED-HALF-UP MEAN (growth is now a stable
# band, reset/classifier are categorical, so bg is the SOLE averaging target). N is a dial; the 4 passes run
# ONCE at population (NOT per re-score) so caching stays the reproducibility mechanism.
BG_FIT_N_READS = 4


def _r1_background_fit_once(row, *, client, model):
    """ONE §B5 bg_fit read -> the full read dict `{background_fit, data_feedback_loop, basis}` (per signed
    cell 178). Evidence is the tested background_fit_evidence blob (operating_characteristics_finding +
    commercial_scale_finding + outcomes_finding). The scorer uses the number; the ledger uses basis + loop."""
    d = _extract_json(run_company_background_fit(
        row["company"], se.background_fit_evidence(row), client=client, model=model))
    return d if isinstance(d, dict) else {}


def _r1_background_fit_read(row, *, client, model, n=BG_FIT_N_READS):
    """Live §B5 v1.24 read -> `{"score", "basis", "loop"}`. The SCORE is the MEAN of N reads ROUNDED HALF-UP
    to an int (before caching, so the floor check sees the rounded mean: 4.5 -> 5 PASSES bg > 4; 4.4 -> 4
    FAILS); each read parses via the scorer's clamp (1-10), failures dropped, ALL N failing -> None score
    (READ-FAILED, DISTINCT from a low score). A representative `basis` + `loop` are captured for the ledger's
    bg rationale (2026-07-02) — the score math is UNCHANGED. Runs ONCE at cache population (byte-stable)."""
    reads = [_r1_background_fit_once(row, client=client, model=model) for _ in range(n)]
    vals = [v for v in (se._bg_score_or_none(d.get("background_fit")) for d in reads) if v is not None]
    score = se.round_half_up(sum(vals) / len(vals)) if vals else None
    basis = next((se._safe_text(d.get("basis")) for d in reads if se._safe_text(d.get("basis"))), "")
    loop = next((se._norm_enum(d.get("data_feedback_loop")) for d in reads
                 if se._norm_enum(d.get("data_feedback_loop")) in ("yes", "no")), "")
    return {"score": score, "basis": basis, "loop": loop}


def _r1_reset_read(row, *, client, model):
    """Live §B4 v1.16 hardened reset re-emit over the row's org_events_finding -> the reset_events list
    (substance-classified). Returns the events ONLY (no row mutation); the events are applied deterministically
    at score time via `_r1_apply_reset`."""
    raw = run_company_reset(row["company"], str(row.get("org_events_finding") or ""), client=client, model=model)
    events = _extract_json(raw).get("reset_events", [])
    return events if isinstance(events, list) else []


def _r1_apply_reset(row, reset_events):
    """Return a COPY of ``row`` whose fit_brief_json.reset_evidence carries ``reset_events`` — so flatten ->
    eligibility -> scoring all read the hardened reset. Pure (does not mutate the input row), so scoring off
    a cache is reproducible."""
    r = dict(row)
    fbj = r.get("fit_brief_json")
    parsed = {}
    if isinstance(fbj, dict):
        parsed = dict(fbj)
    elif isinstance(fbj, str) and fbj.strip():
        try:
            parsed = json.loads(fbj)
        except (ValueError, TypeError):
            parsed = {}
    parsed["reset_evidence"] = {"reset_events": reset_events if isinstance(reset_events, list) else []}
    r["fit_brief_json"] = json.dumps(parsed)
    return r


def _r1_floor_eligible(row, classifier_read, reset_events) -> bool:
    """A company gets bg_fit + growth reads ONLY if it passes PATH + AGENCY and is a consumer (background_fit
    applies) — a floored company is P3 with no LLM spend. Reset (for AGENCY) is read off the FLATTENED row
    with the hardened reset applied, via the strict reader (consistent with score_company)."""
    flat = se.flatten_checkpoint_row(_r1_apply_reset(row, reset_events))
    business_model, _ = se.business_model_for(
        row.get("company"), classifier_read["who_uses"], classifier_read["who_pays"],
        classifier_read["who_uses_confidence"])
    path_passed, _ = se.path_gate(business_model, flat)
    key = se._norm_company(row.get("company"))
    stage = se._norm_stage(flat.get("funding_stage"))
    if key in se.DOCUMENTED_STAGE_OVERRIDES:
        stage = se.DOCUMENTED_STAGE_OVERRIDES[key]
    agency_passed, _, _ = se.agency_gate(stage, se.reset_signal_for_row(flat), ipo_status=flat.get("ipo_status"))
    return path_passed and agency_passed and se.background_fit_applies(classifier_read["who_uses"])


def take_r1_reads(df, *, client, model=DEFAULT_MODEL, cache=None, refresh=None, progress=None):
    """Take each company's four §B scoring reads ONCE (§B2 classifier, §B4 hardened reset, §B6 growth, §B5
    bg_fit) and PERSIST them in ``cache`` (a dict keyed by company). A company already in ``cache`` is
    REUSED (its frozen reads — no LLM re-call), UNLESS it is named in ``refresh`` (a deliberate re-take,
    logged). Floored companies get None growth/bg_fit (no spend). Returns the populated cache (v1.22 —
    caching IS the reproducibility mechanism; temp-0 is not available on this model)."""
    cache = cache if cache is not None else {}
    refresh = {se._norm_company(c) for c in (refresh or [])}
    took = 0
    for _, srow in df.iterrows():
        row = dict(srow)
        co = se._norm_company(row.get("company"))
        if co in cache and co not in refresh:
            continue  # reuse the frozen reads — reproducible, no re-call
        if co in cache and co in refresh and progress:
            progress(f"R1 --refresh: re-taking reads for {co}")
        reset_events = _r1_reset_read(row, client=client, model=model)
        classifier = _r1_classifier_read(row, client=client, model=model)
        eligible = _r1_floor_eligible(row, classifier, reset_events)
        # 2026-07-02 UNIFORM SCORING (MASTER_REDESIGN_SPEC §4): score EVERY company — a floor caps PRIORITY,
        # not scoring. Growth is read for ALL companies; background_fit is read for CONSUMER companies only
        # (bg is a consumer measure — a B2B/professional company has no consumer end-user, so bg is n/a BY
        # DEFINITION, not a cost skip). `eligible` (path+agency+consumer) is now only a reporting metric.
        business_model, _ = se.business_model_for(
            row.get("company"), classifier["who_uses"], classifier["who_pays"], classifier["who_uses_confidence"])
        consumer = business_model in ("B2C", "B2B2C")
        bg = (_r1_background_fit_read(row, client=client, model=model) if consumer
              else {"score": None, "basis": "", "loop": ""})
        cache[co] = {
            "reset_events": reset_events,
            "classifier": classifier,
            "eligible": eligible,
            "business_model": business_model,
            "growth_read": _r1_growth_read(row, client=client, model=model),
            "background_fit": bg["score"],
            "background_fit_basis": bg["basis"],
            "background_fit_loop": bg["loop"],
        }
        took += 1
    if progress:
        n_elig = sum(1 for c in cache.values() if c["eligible"])
        progress(f"R1 reads: took {took} (reused {len(cache) - took}); {n_elig} floor-eligible / {len(cache)}")
    return cache


def score_r1_from_cache(df, cache):
    """Score the roster PURELY off the persisted read-cache (NO LLM). Deterministic function of the cache →
    calling it twice yields an identical roster (the reproducibility proof). Applies each company's cached
    hardened reset, then scores via `score_checkpoint_row`."""
    roster = []
    for _, srow in df.iterrows():
        row = dict(srow)
        c = cache[se._norm_company(row.get("company"))]
        roster.append(se.score_checkpoint_row(
            _r1_apply_reset(row, c["reset_events"]),
            classifier_read=c["classifier"], growth_read=c["growth_read"], background_fit=c["background_fit"],
            background_fit_basis=c.get("background_fit_basis"), data_feedback_loop=c.get("background_fit_loop")))
    return roster


def run_r1(df, *, client, model=DEFAULT_MODEL, cache=None, refresh=None, progress=None):
    """§B7 v1.22 CACHING R1 re-validation over a raw checkpoint DataFrame. Takes each company's four scoring
    reads ONCE (or reuses ``cache``), persists them, and scores OFF the cache — reproducible BY CONSTRUCTION
    (a re-score reads the same frozen values → identical tiers; no model-level determinism needed). Returns
    the `structured_evidence.tally_r1` report + ``reset_reads`` (hardened emit per company) + ``cache`` (pass
    it back to re-score without re-calling; ``refresh=[company]`` re-takes named companies' reads)."""
    cache = take_r1_reads(df, client=client, model=model, cache=cache, refresh=refresh, progress=progress)
    roster = score_r1_from_cache(df, cache)
    report = se.tally_r1(roster)
    report["reset_reads"] = {
        co: {"events": c["reset_events"], "fires": se.derive_reset_signal({"reset_events": c["reset_events"]})}
        for co, c in cache.items()
    }
    report["cache"] = cache
    report["roster"] = roster   # the full per-company score records (with rationale passthrough) — the ledger's input
    if progress:
        progress(f"R1 scored off cache: tally={report['tally']} | review_set={report['review_set_size']}")
    return report
