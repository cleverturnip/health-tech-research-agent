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

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

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

    Faithful port of the notebook ``call_openai`` (STEP 3): same request shape,
    same retry behavior (retry only on ``RateLimitError`` with ``90 * attempt``
    second waits; ``APIError`` re-raises immediately; ``RuntimeError`` after the
    retries are exhausted). ``client``/``model``/``sleep_fn`` are injected.
    """
    for attempt in range(1, max_retries + 1):
        try:
            kwargs = {
                "model": model,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
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


# =============================================================================
# STEP 4 - Raw research functions (verbatim prompts; web search enabled)
# =============================================================================


def search_funding(research_query, *, client, model: str = DEFAULT_MODEL) -> str:
    prompt = f"""
Use live web search to find the latest credible funding, valuation, stage, investors, and company maturity signals for:

{research_query}

Look specifically for:
- latest funding round
- total funding
- valuation
- named investors
- company stage
- major acquisitions or strategic investments
- IPO/S-1/public company status if applicable
- evidence that funding supports growth versus survival

Important:
- Prefer company announcements, SEC filings, Crunchbase/PitchBook summaries, TechCrunch, Forbes, Business Insider, Fierce Healthcare, MobiHealthNews, Healthcare Dive, STAT, Rock Health, or reputable investor/VC pages.
- Do not overstate uncertain funding information.
- If source quality is weak, say so.

Return exactly 1 bullet.
Include source name and date when available.
If none found, say "No strong public funding evidence found."
Keep under 100 words.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=300
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

Return exactly 1 bullet.
Include source name and date when available.
If none found, say "No strong public institutional signal found."
Keep under 120 words.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=350
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

Return exactly 1 bullet.
Include source name and date when available.
If none found, say "No strong public outcomes evidence found."
Keep under 120 words.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=350
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

Return exactly 1 bullet.
Include source name and date when available.
If none found, say "No strong public commercial scale evidence found."
Keep under 150 words.
"""
    return call_openai(
        prompt, client=client, model=model, use_web_search=True, max_output_tokens=450
    )


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

Scale signal classification rules:

commercial_scale_signal:
- Use "strong" only when there is credible revenue, ARR, run-rate, paid-customer scale, subscriber/member scale, strong revenue growth, renewal/retention, repeat usage, pricing power, or credible third-party estimated revenue/run-rate.
- Use "moderate" when there is a real business model, visible pricing, some usage/customer evidence, or indirect monetization evidence, but no strong public revenue, paid-user, retention, or third-party revenue estimate.
- Use "weak" when there is pricing or a D2C model but little evidence of actual scale.
- Use "none" when there is no meaningful public monetization evidence.

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
  "role_timing_assessment": {{
    "company_maturity_read": "early / early-growth / scale-up / late-stage / public / unclear",
    "likely_agency_level": "high / medium / low / role-dependent",
    "stage_timing_fit": "ideal / good / borderline / too late / unclear",
    "why_now_or_why_not": "short explanation of whether Katelynd can enter with high agency now",
    "timing_penalty_applied": true
  }},
  "scale_signal_assessment": {{
    "commercial_scale_signal": "strong / moderate / weak / none",
    "commercial_scale_signal_reason": "short reason",
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
    """A checkpoint row is complete iff all seven research columns are non-blank."""
    return all(_is_nonblank(row.get(col, "")) for col in REQUIRED_RESEARCH_COLUMNS)


def _build_latest_status_findings(funding, payer, outcomes, commercial) -> str:
    """Assemble the four findings into the synthesis input (verbatim STEP 7 layout)."""
    return f"""
Funding:
{funding}

Payer / institutional signal:
{payer}

Outcomes:
{outcomes}

Commercial scale / revenue quality:
{commercial}
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
    sleep_fn=time.sleep,
    validate_json: bool = True,
) -> ResearchBatchResult:
    """Run research + fit brief for each company, with per-company recovery.

    Faithful port of notebook STEP 7:

    * Resume: a checkpoint row with all ``REQUIRED_RESEARCH_COLUMNS`` non-blank is
      "complete"; those companies are skipped (``reused``) and not re-researched.
    * After each successful company the checkpoint is written atomically and
      (optionally) mirrored, so a runtime loss never loses completed work.
    * The four web searches run with the faithful wait between them (injected
      ``sleep_fn``), then the fit brief is synthesized.

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
            funding = search_funding(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            payer = search_payer_signal(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            outcomes = search_outcomes(research_query, client=client, model=model)
            sleep_fn(wait_between_searches)

            commercial = search_commercial_scale(research_query, client=client, model=model)

            latest_status_findings = _build_latest_status_findings(
                funding, payer, outcomes, commercial
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
