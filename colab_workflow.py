"""
Health Tech Research Agent - Colab Workflow

This file mirrors the active Google Colab workflow.

Current execution environment:

* Google Colab
* Google Drive for persistent storage
* OpenAI API for fit synthesis
* CSV/XLSX exports for dashboard outputs

Important:

* This file is currently a source-of-truth reference for copy/paste Colab cells.
* It is not yet a fully modular script.
* As the workflow stabilizes, cells should be converted into functions and eventually into a runnable pipeline.
  """

# =============================================================================

# STEP 1 - Environment / imports / setup

# =============================================================================

!pip install -q openai pandas

# =============================================================================

# STEP 2 - Company/source config

# =============================================================================

import os
import time
import json
import pandas as pd
from datetime import datetime
from openai import OpenAI, RateLimitError, APIError
from google.colab import userdata

# Pull your API key securely from Colab Secrets
os.environ["OPENAI_API_KEY"] = userdata.get("OPENAI_API_KEY")

client = OpenAI()

# Use the same model you are using in the Playground.
# If this errors, copy the exact model name from the Playground "Code" button.
MODEL = "gpt-5.4-mini"

# Rate-limit protection
WAIT_BETWEEN_WEB_SEARCHES = 120  # seconds
MAX_RETRIES = 3

# =============================================================================

# STEP 3 - Search / research helpers

# =============================================================================

def call_openai(prompt, use_web_search=False, max_output_tokens=500):
    """
    Sends a prompt to OpenAI.
    If use_web_search=True, it enables the web search tool.
    Includes retry logic for rate-limit errors.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs = {
                "model": MODEL,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
            }

            if use_web_search:
                kwargs["tools"] = [{"type": "web_search"}]
                kwargs["tool_choice"] = "auto"

            response = client.responses.create(**kwargs)
            return response.output_text

        except RateLimitError as e:
            wait_time = 90 * attempt
            print(f"Rate limit hit. Waiting {wait_time} seconds before retry {attempt}/{MAX_RETRIES}...")
            time.sleep(wait_time)

        except APIError as e:
            print(f"API error: {e}")
            raise

    raise RuntimeError("Max retries reached. Try again later or reduce the company batch size.")

# =============================================================================

# STEP 4 - Raw research functions

# =============================================================================

# Purpose:

# - Funding research

# - Payer / institutional distribution research

# - Outcomes research

# - Commercial scale / revenue-quality research

# 4 - Prompt 1 research functions
# Purpose:
# - Collect structured latest-status research inputs for each company
# - Funding / stage
# - Payer, employer, provider, institutional distribution
# - Outcomes / clinical / engagement evidence
# - Commercial scale / revenue quality
#
# Depends on:
# - call_openai(prompt, use_web_search=True, max_output_tokens=...)

def search_funding(research_query):
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
    return call_openai(prompt, use_web_search=True, max_output_tokens=300)


def search_payer_signal(research_query):
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
    return call_openai(prompt, use_web_search=True, max_output_tokens=350)


def search_outcomes(research_query):
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
    return call_openai(prompt, use_web_search=True, max_output_tokens=350)


def search_commercial_scale(research_query):
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
    return call_openai(prompt, use_web_search=True, max_output_tokens=450)

# =============================================================================

# STEP 5 - Company fit synthesis prompt

# =============================================================================

# Purpose:

# - Convert raw research findings into structured JSON

# - Score thesis fit, PMF/scale, evidence confidence, role fit, timing

# - Output scale signal fields

# - Use priority gate logic

# =============================================================================
# STEP 5 - Company fit synthesis prompt
# =============================================================================
# Purpose:
# - Convert raw research findings into structured company fit JSON
# - Score thesis fit, PMF/scale, evidence confidence, Katelynd role fit, and operator timing
# - Classify commercial, institutional, and outcomes scale signals explicitly
# - Use native P0/P1/P2/P3/P4 priority labels
# - Use scale-engine logic:
#   revenue quality/commercial traction OR institutional distribution can each be a primary scale engine
# - Do not let high role fit or thesis relevance override weak PMF/scale evidence

def run_company_fit_brief(company_name, latest_status_findings):
    prompt = f"""
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
- P1: Near-priority target
  Use for former P1-border companies: companies that are differentiated from ordinary P2s and may become active targets after a small amount of diligence, but are not as clean as P0. These usually have strong thesis/role/timing fit and credible scale, but have a meaningful gap, caveat, or missing pillar.
- P2: Worth deeper diligence
  Use when the company clears the P2 priority gate but still has evidence gaps, timing ambiguity, role-fit questions, missing internal metrics, or one major missing pillar.
- P3: Watch list
  Use when the company has some fit or interesting signals, but does not clear the P2 priority gate because scale, evidence, role fit, or timing is not strong enough yet.
- P4: Low priority / likely reject
  Use when the company does not currently fit the thesis, has weak scale path, weak role fit, poor timing, or no compelling evidence of relevance.

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
   Measures whether Katelynd's background fits the company's likely needs.

5. operator_timing_score
   Measures whether this is the right moment for her kind of operator role.

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
  "commercial_scale_assessment": "plain-English assessment of revenue quality, paid-customer scale, retention, pricing power, CAC/margin if available, and whether revenue is reported, estimated, or inferred",
  "pmf_scale_assessment": "plain-English assessment explaining the strongest scale engine, secondary scale engine if any, outcomes/product-value support, and key caveats",
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
  "priority_level": "P0: Highest-priority target / P1: Near-priority target / P2: Worth deeper diligence / P3: Watch list / P4: Low priority / likely reject",
  "calibration_flag": "short flag if needed, otherwise blank string",
  "final_takeaway": "1-3 sentence concise conclusion"
}}
"""
    return call_openai(prompt, use_web_search=False, max_output_tokens=6500)

# =============================================================================

# STEP 6 - Batch config / paths / company list

# =============================================================================

# 6 - Batch config / file paths
# Run this every time:
# - you start a new batch
# - runtime reconnects/restarts
# - before Step 7

from pathlib import Path

# CHANGE THIS FOR EACH NEW BATCH
BATCH_NAME = "pmf_scale_rubric_d2c_rerun_1"

# Local runtime folder
research_batches_folder = Path("research_batches")
research_batches_folder.mkdir(parents=True, exist_ok=True)

# Standard batch paths
batch_checkpoint_path = research_batches_folder / f"{BATCH_NAME}_checkpoint.csv"
batch_raw_export_path = research_batches_folder / f"{BATCH_NAME}_raw.csv"
batch_summary_export_path = research_batches_folder / f"{BATCH_NAME}_summary.csv"

print("Batch config set.")
print("BATCH_NAME:", BATCH_NAME)
print("batch_checkpoint_path:", batch_checkpoint_path)
print("batch_raw_export_path:", batch_raw_export_path)
print("batch_summary_export_path:", batch_summary_export_path)

# =============================================================================

# STEP 6B - Standard cross-batch checkpoint recovery

# =============================================================================

# 6B - Seed current batch checkpoint from all prior research sources
# Purpose:
# - Define the current batch companies
# - Reuse prior completed research by company, even if saved under a different batch name
# - Search exact current checkpoint, all Drive research_batches files, and raw archive
# - Seed the current local + Drive checkpoint so Step 7 only runs missing companies
#
# Edit the companies list in this cell for each new batch.
# Step 7 should no longer define companies.

import pandas as pd
import shutil
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

# -----------------------------
# Safety checks
# -----------------------------

if "BATCH_NAME" not in globals():
    raise NameError("STOP: BATCH_NAME is not defined. Run Step 6 first.")

if "batch_checkpoint_path" not in globals():
    local_batches_folder = Path("research_batches")
    local_batches_folder.mkdir(parents=True, exist_ok=True)
    batch_checkpoint_path = local_batches_folder / f"{BATCH_NAME}_checkpoint.csv"

# -----------------------------
# Current batch company list
# -----------------------------
# Commercial-scale backfill batch:
# Focus: D2C / cash-pay / hybrid companies where revenue quality,
# retention, subscriber growth, acquisition efficiency, and margin structure
# could materially change fit assessment.

companies = [
    {
        "company": "Oura",
        "research_query": "Oura ring revenue growth subscribers paid members retention renewal rate D2C employer payer insurance partnerships outcomes funding"
    },
    {
        "company": "Function Health",
        "research_query": "Function Health revenue growth memberships subscribers retention D2C employer partnerships funding outcomes commercial scale"
    },
    {
        "company": "ZOE",
        "research_query": "ZOE personalized nutrition revenue growth subscribers retention D2C employer payer partnerships outcomes funding commercial scale"
    },
    {
        "company": "Signos",
        "research_query": "Signos CGM metabolic health revenue growth subscribers retention D2C employer payer insurance outcomes funding commercial scale"
    },
    {
        "company": "Levels Health",
        "research_query": "Levels Health metabolic health CGM revenue growth subscribers retention D2C funding outcomes commercial scale"
    },
    {
        "company": "InsideTracker",
        "research_query": "InsideTracker revenue growth subscribers retention memberships D2C employer partnerships funding outcomes commercial scale"
    },
    {
        "company": "Noom Med",
        "research_query": "Noom Med revenue growth subscribers retention employer payer insurance GLP-1 weight loss outcomes funding commercial scale"
    },
    {
        "company": "Oova",
        "research_query": "Oova fertility hormone testing revenue growth subscribers retention D2C employer payer insurance partnerships outcomes funding commercial scale"
    },
    {
        "company": "Outcomes4Me",
        "research_query": "Outcomes4Me cancer patient platform revenue growth users retention pharma partnerships payer provider outcomes funding commercial scale"
    }
]

current_batch_company_names = [
    item["company"] if isinstance(item, dict) else item
    for item in companies
]

# -----------------------------
# Paths
# -----------------------------

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"
drive_batches_folder.mkdir(parents=True, exist_ok=True)

drive_archive_path = drive_folder / "health_tech_raw_research_ARCHIVE.csv"
drive_checkpoint_path = drive_batches_folder / f"{BATCH_NAME}_checkpoint.csv"

required_current_schema_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

print("Batch name:", BATCH_NAME)
print("Current batch companies:", current_batch_company_names)
print("Local checkpoint:", batch_checkpoint_path)
print("Drive checkpoint:", drive_checkpoint_path)
print("Drive batches folder:", drive_batches_folder)
print("Raw archive:", drive_archive_path)

# -----------------------------
# Helpers
# -----------------------------

def nonblank(value):
    return pd.notna(value) and str(value).strip() != ""

def source_priority_score(source_name):
    """
    Higher = preferred if duplicate complete rows exist.
    """
    priority = {
        "local_exact_batch_checkpoint": 4,
        "drive_exact_batch_checkpoint": 3,
        "drive_research_batches_any_batch": 2,
        "raw_archive_any_batch": 1
    }
    return priority.get(source_name, 0)

def load_csv_safely(path):
    try:
        temp = pd.read_csv(path)
        if "company" not in temp.columns:
            return None
        return temp
    except Exception as e:
        print(f"Skipping unreadable CSV: {path} | {e}")
        return None

def prepare_source_df(source_df, source_name, source_file):
    """
    Adds completeness scoring and filters to current batch companies.
    """
    if source_df is None or source_df.empty:
        return pd.DataFrame()

    df_source = source_df.copy()

    for col in required_current_schema_cols:
        if col not in df_source.columns:
            df_source[col] = ""

    df_source = df_source[
        df_source["company"].isin(current_batch_company_names)
    ].copy()

    if df_source.empty:
        return pd.DataFrame()

    for col in required_current_schema_cols:
        df_source[f"has_{col}"] = df_source[col].apply(nonblank)

    completeness_cols = [f"has_{col}" for col in required_current_schema_cols]

    df_source["current_schema_completeness"] = df_source[completeness_cols].sum(axis=1)
    df_source["is_current_schema_complete"] = df_source[completeness_cols].all(axis=1)
    df_source["seed_source"] = source_name
    df_source["source_file"] = str(source_file)
    df_source["source_priority"] = source_priority_score(source_name)

    return df_source

def missing_fields_for_row(row):
    return [
        col for col in required_current_schema_cols
        if not nonblank(row.get(col, ""))
    ]

# -----------------------------
# Gather all possible recovery sources
# -----------------------------

candidate_frames = []

# 1. Local exact checkpoint
if batch_checkpoint_path.exists():
    local_df = load_csv_safely(batch_checkpoint_path)
    prepared = prepare_source_df(
        local_df,
        source_name="local_exact_batch_checkpoint",
        source_file=batch_checkpoint_path
    )
    if not prepared.empty:
        candidate_frames.append(prepared)
else:
    print("\nNo local exact-batch checkpoint found.")

# 2. Drive exact checkpoint
if drive_checkpoint_path.exists():
    drive_checkpoint_df = load_csv_safely(drive_checkpoint_path)
    prepared = prepare_source_df(
        drive_checkpoint_df,
        source_name="drive_exact_batch_checkpoint",
        source_file=drive_checkpoint_path
    )
    if not prepared.empty:
        candidate_frames.append(prepared)
else:
    print("\nNo Drive exact-batch checkpoint found.")

# 3. All Drive research batch CSVs, any batch name
drive_batch_csvs = sorted(drive_batches_folder.glob("*.csv"))

print(f"\nScanning Drive research_batches CSVs: {len(drive_batch_csvs)} files found")

for path in drive_batch_csvs:
    # Skip exact current checkpoint here because already handled above.
    if path == drive_checkpoint_path:
        continue

    temp_df = load_csv_safely(path)

    if temp_df is None:
        continue

    prepared = prepare_source_df(
        temp_df,
        source_name="drive_research_batches_any_batch",
        source_file=path
    )

    if not prepared.empty:
        candidate_frames.append(prepared)

# 4. Raw archive, any prior batch
if drive_archive_path.exists():
    archive_df = load_csv_safely(drive_archive_path)
    prepared = prepare_source_df(
        archive_df,
        source_name="raw_archive_any_batch",
        source_file=drive_archive_path
    )
    if not prepared.empty:
        candidate_frames.append(prepared)
else:
    print("\nNo raw archive found in Drive.")

# -----------------------------
# Evaluate candidates
# -----------------------------

if not candidate_frames:
    print("\nNo prior rows found for current batch companies.")
    print("Step 7 will run all current batch companies from scratch.")
else:
    candidates = pd.concat(candidate_frames, ignore_index=True)

    # For reporting: best available row per company, even if incomplete
    best_available = (
        candidates
        .sort_values(
            by=[
                "company",
                "is_current_schema_complete",
                "current_schema_completeness",
                "source_priority",
                "date_researched"
            ],
            ascending=[True, False, False, False, False]
        )
        .drop_duplicates(subset=["company"], keep="first")
        .reset_index(drop=True)
    )

    print("\nBest prior row found per company:")
    display(
        best_available[
            [
                col for col in [
                    "company",
                    "date_researched",
                    "seed_source",
                    "source_file",
                    "current_schema_completeness",
                    "is_current_schema_complete",
                    "funding_finding",
                    "payer_institutional_finding",
                    "outcomes_finding",
                    "commercial_scale_finding"
                ]
                if col in best_available.columns
            ]
        ]
    )

    incomplete_best = best_available[
        ~best_available["is_current_schema_complete"]
    ].copy()

    if not incomplete_best.empty:
        missing_report = []

        for _, row in incomplete_best.iterrows():
            missing_report.append({
                "company": row["company"],
                "seed_source": row.get("seed_source", ""),
                "source_file": row.get("source_file", ""),
                "date_researched": row.get("date_researched", ""),
                "missing_fields": ", ".join(missing_fields_for_row(row))
            })

        print("\nPrior rows exist but are NOT reusable under the current schema:")
        display(pd.DataFrame(missing_report))

    # Reusable = complete current-schema rows only
    reusable = candidates[
        candidates["is_current_schema_complete"]
    ].copy()

    if reusable.empty:
        print("\nNo complete current-schema prior rows found.")
        print("Step 7 will run all current batch companies from scratch.")
    else:
        # Choose best complete row per company.
        reusable_best = (
            reusable
            .sort_values(
                by=[
                    "company",
                    "source_priority",
                    "date_researched"
                ],
                ascending=[True, False, False]
            )
            .drop_duplicates(subset=["company"], keep="first")
            .reset_index(drop=True)
        )

        reusable_checkpoint_rows = reusable_best[required_current_schema_cols].copy()

        # Save seeded checkpoint locally and to Drive
        batch_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        reusable_checkpoint_rows.to_csv(batch_checkpoint_path, index=False)
        shutil.copy(batch_checkpoint_path, drive_checkpoint_path)

        print("\nSeeded checkpoint created from complete prior research.")
        print("Seeded companies:", reusable_checkpoint_rows["company"].tolist())
        print("Checkpoint rows:", reusable_checkpoint_rows.shape[0])
        print("Local checkpoint:", batch_checkpoint_path)
        print("Drive checkpoint:", drive_checkpoint_path)

# -----------------------------
# Show what Step 7 will still run
# -----------------------------

if batch_checkpoint_path.exists():
    seeded_df = pd.read_csv(batch_checkpoint_path)
    seeded_companies = set(seeded_df["company"].tolist())
else:
    seeded_df = pd.DataFrame(columns=["company"])
    seeded_companies = set()

companies_to_run = [
    company for company in current_batch_company_names
    if company not in seeded_companies
]

print("\nCompanies already complete / reusable:")
print(sorted(seeded_companies) if seeded_companies else "None")

print("\nCompanies Step 7 still needs to run:")
print(companies_to_run if companies_to_run else "None")

if not seeded_df.empty:
    print("\nSeeded checkpoint preview:")
    display(seeded_df)

# =============================================================================

# STEP 7 - Run research + fit briefs

# =============================================================================

# Step 7 - Run companies
# Purpose:
# - Run research only for companies missing from the seeded/current checkpoint
# - Save local + Drive checkpoint after each company
# - Includes commercial_scale_finding

from pathlib import Path
import pandas as pd
from datetime import datetime
import time
import shutil
from google.colab import drive

# -----------------------------
# Safety checks
# -----------------------------

if "BATCH_NAME" not in globals():
    raise NameError("STOP: BATCH_NAME is not defined. Run Step 6 first.")

if "companies" not in globals():
    raise NameError(
        "STOP: companies list is not defined. Run Step 6B first."
    )

if "batch_checkpoint_path" not in globals():
    local_batches_folder = Path("research_batches")
    local_batches_folder.mkdir(parents=True, exist_ok=True)
    batch_checkpoint_path = local_batches_folder / f"{BATCH_NAME}_checkpoint.csv"

checkpoint_path = batch_checkpoint_path

required_current_schema_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

def nonblank(value):
    return pd.notna(value) and str(value).strip() != ""

def row_is_current_schema_complete(row):
    return all(nonblank(row.get(col, "")) for col in required_current_schema_cols)

# -----------------------------
# Drive checkpoint path
# -----------------------------

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"
drive_batches_folder.mkdir(parents=True, exist_ok=True)

drive_checkpoint_path = drive_batches_folder / f"{BATCH_NAME}_checkpoint.csv"

# -----------------------------
# Load checkpoint if it exists
# -----------------------------

if checkpoint_path.exists():
    df_existing = pd.read_csv(checkpoint_path)

    for col in required_current_schema_cols:
        if col not in df_existing.columns:
            df_existing[col] = ""

    df_existing["is_current_schema_complete"] = df_existing.apply(
        row_is_current_schema_complete,
        axis=1
    )

    incomplete_existing = df_existing[
        ~df_existing["is_current_schema_complete"]
    ].copy()

    if not incomplete_existing.empty:
        print("Found incomplete checkpoint rows. These will be rerun:")
        display(
            incomplete_existing[
                [
                    col for col in [
                        "company",
                        "date_researched",
                        "funding_finding",
                        "payer_institutional_finding",
                        "outcomes_finding",
                        "commercial_scale_finding"
                    ]
                    if col in incomplete_existing.columns
                ]
            ]
        )

    df_existing_complete = df_existing[
        df_existing["is_current_schema_complete"]
    ].copy()

    df_existing_complete = df_existing_complete[
        required_current_schema_cols
    ].copy()

    results = df_existing_complete.to_dict("records")
    completed_companies = set(df_existing_complete["company"].tolist())

    print(f"Loaded checkpoint with {len(results)} complete companies:", completed_companies)

else:
    results = []
    completed_companies = set()
    print("No existing checkpoint found. Starting fresh.")

# -----------------------------
# Run missing companies
# -----------------------------

for company_item in companies:
    if isinstance(company_item, dict):
        company = company_item["company"]
        research_query = company_item["research_query"]
    else:
        company = company_item
        research_query = company_item

    if company in completed_companies:
        print(f"Skipping {company}; already completed in checkpoint.")
        continue

    print(f"\n--- Researching {company} ---")

    funding = search_funding(research_query)
    print("Funding:", funding)

    time.sleep(WAIT_BETWEEN_WEB_SEARCHES)

    payer = search_payer_signal(research_query)
    print("Payer / institutional signal:", payer)

    time.sleep(WAIT_BETWEEN_WEB_SEARCHES)

    outcomes = search_outcomes(research_query)
    print("Outcomes:", outcomes)

    time.sleep(WAIT_BETWEEN_WEB_SEARCHES)

    commercial_scale = search_commercial_scale(research_query)
    print("Commercial scale:", commercial_scale)

    latest_status_findings = f"""
Funding:
{funding}

Payer / institutional signal:
{payer}

Outcomes:
{outcomes}

Commercial scale / revenue quality:
{commercial_scale}
"""

    fit_brief = run_company_fit_brief(company, latest_status_findings)

    new_record = {
        "company": company,
        "date_researched": datetime.now().strftime("%Y-%m-%d"),
        "funding_finding": funding,
        "payer_institutional_finding": payer,
        "outcomes_finding": outcomes,
        "commercial_scale_finding": commercial_scale,
        "fit_brief_json": fit_brief
    }

    results.append(new_record)
    completed_companies.add(company)

    df = pd.DataFrame(results)

    # Keep one row per company, latest run wins
    df = df.drop_duplicates(subset=["company"], keep="last").reset_index(drop=True)

    # Save local checkpoint
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(checkpoint_path, index=False)

    # Save Drive checkpoint after each company
    shutil.copy(checkpoint_path, drive_checkpoint_path)

    print(f"Checkpoint saved after {company}.")
    print("Local checkpoint:", checkpoint_path)
    print("Drive checkpoint:", drive_checkpoint_path)
    print(f"Finished {company}. Waiting before next company...")

    time.sleep(WAIT_BETWEEN_WEB_SEARCHES)

# -----------------------------
# Final df for downstream steps
# -----------------------------

if checkpoint_path.exists():
    df = pd.read_csv(checkpoint_path)
else:
    df = pd.DataFrame(results)

print("\nStep 7 complete.")
print("df shape:", df.shape)
print("companies in df:", df["company"].tolist() if "company" in df.columns else [])

df

# =============================================================================

# STEP 8 - Save current batch checkpoint

# =============================================================================

print("About to save CURRENT BATCH ONLY.")
print("df shape:", df.shape)
print("companies:", df["company"].tolist())

df.to_csv(batch_checkpoint_path, index=False)

print("Saved current batch checkpoint to:")
print(batch_checkpoint_path)

# =============================================================================

# STEP 8A - Save raw research archive

# =============================================================================

# 8A - Save raw research archive
# Purpose:
# - Preserve the full raw research layer permanently
# - Save current batch raw research to Google Drive
# - Append current batch raw research to a permanent archive
# - Download local copies so Colab runtime loss does not wipe the work
# - Prevent incomplete raw records from being archived
# - Includes commercial_scale_finding for revenue quality / D2C scale mechanics

import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil
from google.colab import drive, files

# -----------------------------
# Safety checks
# -----------------------------

if "df" not in globals():
    raise NameError("STOP: df does not exist. Run Step 7 / Step 8 before running 8A.")

if "company" not in df.columns:
    raise ValueError("STOP: df does not have a company column. This does not look like the raw research dataframe.")

if "BATCH_NAME" not in globals():
    raise NameError("STOP: BATCH_NAME is not defined. Run Step 6 before running 8A.")

required_raw_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

missing_cols = [col for col in required_raw_cols if col not in df.columns]

if missing_cols:
    raise ValueError(
        f"STOP: df is missing required raw research columns: {missing_cols}. "
        "If this is an old checkpoint, rerun the companies under the new Step 7 schema."
    )

if df.shape[0] == 0:
    raise ValueError("STOP: df has zero rows. Nothing to archive.")

# -----------------------------
# Blank-field protection for current batch
# -----------------------------

blank_issues = []

for col in required_raw_cols:
    blank_mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
    if blank_mask.any():
        for company in df.loc[blank_mask, "company"].tolist():
            blank_issues.append({
                "company": company,
                "blank_field": col
            })

if blank_issues:
    blank_df = pd.DataFrame(blank_issues)
    print("STOP: Blank raw research fields found in current batch. Repair these before archiving.")
    display(blank_df)
    raise ValueError("Blank raw research fields found. Do not archive until repaired.")

# -----------------------------
# Validate fit_brief_json parses for current batch
# -----------------------------

import json

json_issues = []

for idx, row in df.iterrows():
    company = row["company"]
    value = row["fit_brief_json"]

    try:
        json.loads(str(value))
    except Exception as e:
        json_issues.append({
            "company": company,
            "issue": str(e)
        })

if json_issues:
    json_issue_df = pd.DataFrame(json_issues)
    print("STOP: Some fit_brief_json values are not valid JSON. Repair before archiving.")
    display(json_issue_df)
    raise ValueError("Invalid fit_brief_json found. Do not archive until repaired.")

# -----------------------------
# Add archive metadata
# -----------------------------

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

raw_batch_df = df.copy()

raw_batch_df["batch_name"] = BATCH_NAME
raw_batch_df["archive_saved_at"] = timestamp
raw_batch_df["archive_record_id"] = (
    raw_batch_df["batch_name"].astype(str)
    + "__"
    + raw_batch_df["company"].astype(str).str.replace(" ", "_", regex=False)
    + "__"
    + raw_batch_df["archive_saved_at"].astype(str)
)

# -----------------------------
# Local runtime paths
# -----------------------------

local_batches_folder = Path("research_batches")
local_batches_folder.mkdir(parents=True, exist_ok=True)

current_batch_raw_path = local_batches_folder / f"{BATCH_NAME}_raw_{timestamp}.csv"
current_batch_checkpoint_path = local_batches_folder / f"{BATCH_NAME}_checkpoint.csv"
raw_archive_path = Path("health_tech_raw_research_ARCHIVE.csv")

# -----------------------------
# Mount Google Drive and pull latest archive if it exists
# -----------------------------

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"

drive_folder.mkdir(parents=True, exist_ok=True)
drive_batches_folder.mkdir(parents=True, exist_ok=True)

drive_raw_archive_path = drive_folder / "health_tech_raw_research_ARCHIVE.csv"

# If Drive already has an archive, use that as the starting source of truth.
# This prevents a fresh Colab runtime from accidentally creating a tiny archive.
if drive_raw_archive_path.exists():
    shutil.copy(drive_raw_archive_path, raw_archive_path)
    print("Loaded existing raw archive from Google Drive.")
else:
    print("No existing raw archive found in Google Drive. Creating a new one.")

# -----------------------------
# Save current batch raw files locally
# -----------------------------

raw_batch_df.to_csv(current_batch_raw_path, index=False)
raw_batch_df.to_csv(current_batch_checkpoint_path, index=False)

# -----------------------------
# Append to archive
# -----------------------------

if raw_archive_path.exists():
    existing_archive = pd.read_csv(raw_archive_path)

    # Backward-compatible archive schema migration.
    # Older archived rows may not have commercial_scale_finding.
    # Keep them, but add the column blank so the archive schema is consistent.
    for col in required_raw_cols:
        if col not in existing_archive.columns:
            existing_archive[col] = ""

    for col in ["batch_name", "archive_saved_at", "archive_record_id"]:
        if col not in existing_archive.columns:
            existing_archive[col] = ""

    combined_archive = pd.concat([existing_archive, raw_batch_df], ignore_index=True)
else:
    combined_archive = raw_batch_df.copy()

# Avoid duplicate company records within the same batch if you rerun 8A after a repair.
# Keeps the latest version for each company + batch_name.
combined_archive = combined_archive.drop_duplicates(
    subset=["company", "batch_name"],
    keep="last"
).reset_index(drop=True)

combined_archive.to_csv(raw_archive_path, index=False)

# -----------------------------
# Google Drive save
# -----------------------------

drive_current_batch_raw_path = drive_batches_folder / f"{BATCH_NAME}_raw_{timestamp}.csv"
drive_current_batch_checkpoint_path = drive_batches_folder / f"{BATCH_NAME}_checkpoint.csv"
drive_raw_archive_backup_path = drive_folder / f"health_tech_raw_research_ARCHIVE_backup_{timestamp}.csv"

# Save current batch to Drive
shutil.copy(current_batch_raw_path, drive_current_batch_raw_path)
shutil.copy(current_batch_checkpoint_path, drive_current_batch_checkpoint_path)

# Save updated archive to Drive
shutil.copy(raw_archive_path, drive_raw_archive_path)
shutil.copy(raw_archive_path, drive_raw_archive_backup_path)

# -----------------------------
# Validation output
# -----------------------------

print("Raw research archive saved successfully.")
print()
print("Current batch rows:", raw_batch_df.shape[0])
print("Current batch companies:", raw_batch_df["company"].tolist())
print()
print("Local current batch raw:")
print(current_batch_raw_path)
print()
print("Local raw archive:")
print(raw_archive_path)
print("Archive shape:", combined_archive.shape)
print("Archive company count:", combined_archive["company"].nunique())
print()
print("Google Drive current batch raw:")
print(drive_current_batch_raw_path)
print()
print("Google Drive raw archive:")
print(drive_raw_archive_path)
print()
print("Google Drive archive backup:")
print(drive_raw_archive_backup_path)

print()
print("Current batch raw field check:")
display(
    raw_batch_df[
        [
            "company",
            "funding_finding",
            "payer_institutional_finding",
            "outcomes_finding",
            "commercial_scale_finding"
        ]
    ]
)

# Show archive company counts by batch
print()
print("Archive batch summary:")
display(
    combined_archive
    .groupby("batch_name")
    .agg(
        company_count=("company", "nunique"),
        row_count=("company", "count")
    )
    .reset_index()
)

# -----------------------------
# Download local copies
# -----------------------------

files.download(str(current_batch_raw_path))
files.download(str(raw_archive_path))

# =============================================================================

# STEP 9 - Print raw batch results

# =============================================================================

pd.set_option("display.max_colwidth", None)

print("Printing CURRENT BATCH raw results only.")
print("df shape:", df.shape)
print("companies:", df["company"].tolist())

for idx, row in df.iterrows():
    print("\n" + "="*80)
    print(row["company"])
    print("="*80)
    print("FUNDING:")
    print(row["funding_finding"])
    print("\nPAYER / INSTITUTIONAL:")
    print(row["payer_institutional_finding"])
    print("\nOUTCOMES:")
    print(row["outcomes_finding"])
    print("\nFIT BRIEF:")
    print(row["fit_brief_json"])

# =============================================================================

# STEP 10 - Parse fit brief JSON into score/summary table

# =============================================================================

# Step 10 - Validation summary
# Purpose:
# - Parse fit_brief_json into summary_df
# - Extract scores, recommendation, priority, business model, and commercial-scale assessment
# - Normalize nested/dict outputs into clean text
# - Add calibration flags before export / master update

import json
import re
import pandas as pd

# -----------------------------
# Helpers
# -----------------------------

def clean_json_text(text):
    text = str(text).strip()
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()

def parse_first_json_object(text):
    """
    Parses the first valid JSON object from a text string.
    This handles cases where the model returns valid JSON plus extra text afterward.
    """
    raw = clean_json_text(text)
    start = raw.find("{")

    if start == -1:
        raise ValueError("No JSON object found")

    decoder = json.JSONDecoder()
    parsed, end = decoder.raw_decode(raw[start:])

    return parsed

def extract_score(scores, key):
    value = scores.get(key)

    if isinstance(value, dict):
        return value.get("score")

    return value

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def as_number(value):
    try:
        return float(value)
    except Exception:
        return None

def normalize_jsonish(value):
    """
    Converts nested dict/list fields into readable text for export/display.
    If a dict has a summary field, use that summary.
    Otherwise, convert to a clean JSON string.
    """
    if isinstance(value, dict):
        if "summary" in value and str(value["summary"]).strip() != "":
            return str(value["summary"]).strip()
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)

    if pd.isna(value):
        return ""

    return str(value).strip()

def is_d2c_specific_business_model(business_model_text):
    """
    Detects true D2C / cash-pay companies without over-flagging
    hybrid payer/employer/provider-enabled consumer platforms.
    """
    business_model = safe_text(business_model_text).lower()

    institutional_terms = [
        "b2b2c",
        "payer",
        "employer",
        "provider",
        "benefits",
        "insurance",
        "health plan",
        "government",
        "pharma",
        "medicaid",
        "medicare"
    ]

    has_institutional_path = any(term in business_model for term in institutional_terms)

    appears_d2c = (
        "d2c" in business_model
        or "cash-pay" in business_model
        or "cash pay" in business_model
        or "primarily d2c" in business_model
        or "primarily cash" in business_model
    )

    # Do not treat generic "consumer health platform" as D2C if the classification
    # is clearly hybrid/B2B2C/payer/employer/provider-enabled.
    d2c_specific_review_needed = appears_d2c and not (
        has_institutional_path and "hybrid" in business_model
    )

    return d2c_specific_review_needed

def commercial_signal_is_weak(commercial_scale_finding, commercial_scale_assessment):
    text = (
        safe_text(commercial_scale_finding)
        + " "
        + safe_text(commercial_scale_assessment)
    ).lower()

    weak_phrases = [
        "no strong public commercial scale evidence found",
        "weak evidence",
        "commercial scale evidence is weak",
        "weak-to-moderate",
        "not enough hard evidence",
        "not strongly substantiated",
        "not revenue quality",
        "no credible public revenue",
        "no public revenue",
        "no verified current arr",
        "no public arr",
        "no subscriber count",
        "no retention",
        "no renewal",
        "no cac",
        "no margin"
    ]

    if safe_text(commercial_scale_finding) == "":
        return True

    return any(phrase in text for phrase in weak_phrases)

def build_calibration_flag(row):
    flags = []

    priority = safe_text(row.get("priority_level"))
    business_model = safe_text(row.get("business_model_classification"))

    commercial_scale_finding = safe_text(row.get("commercial_scale_finding"))
    commercial_scale_assessment = safe_text(row.get("commercial_scale_assessment"))

    thesis = as_number(row.get("thesis_fit_score"))
    pmf = as_number(row.get("pmf_scale_score"))
    evidence = as_number(row.get("evidence_confidence_score"))
    role_fit = as_number(row.get("katelynd_role_fit_score"))
    operator_timing = as_number(row.get("operator_timing_score"))

    # P2 evidence / PMF checks
    if priority == "P2: Worth deeper diligence":
        if evidence is not None and evidence < 50:
            flags.append("CHECK: P2 with low evidence")

        if pmf is not None and pmf < 60:
            flags.append("CHECK: P2 with weak PMF/scale")

        if (
            role_fit is not None
            and operator_timing is not None
            and role_fit < 70
            and operator_timing < 70
        ):
            flags.append("CHECK: P2 with weak role/timing fit")

        if (
            evidence is not None
            and pmf is not None
            and (evidence < 65 or pmf < 70)
        ):
            flags.append("REVIEW: P2 with moderate evidence/PMF")

    # Possible P1 under-promotion
    if priority != "P1: High-priority target":
        if (
            thesis is not None
            and pmf is not None
            and evidence is not None
            and role_fit is not None
            and operator_timing is not None
            and thesis >= 90
            and pmf >= 80
            and evidence >= 70
            and role_fit >= 80
            and operator_timing >= 75
        ):
            flags.append("CHECK: possible P1 under-promotion")

    # D2C / commercial-scale checks
    d2c_specific_review_needed = is_d2c_specific_business_model(business_model)
    weak_commercial_signal = commercial_signal_is_weak(
        commercial_scale_finding,
        commercial_scale_assessment
    )

    if (
        d2c_specific_review_needed
        and priority in ["P1: High-priority target", "P2: Worth deeper diligence"]
        and weak_commercial_signal
    ):
        flags.append("REVIEW: D2C priority with weak commercial-scale evidence")

    if (
        d2c_specific_review_needed
        and pmf is not None
        and evidence is not None
        and pmf >= 75
        and evidence < 60
    ):
        flags.append("REVIEW: D2C scale claim with moderate/weak evidence confidence")

    return " | ".join(flags)

# -----------------------------
# Parse fit briefs
# -----------------------------

summary_rows = []

for _, row in df.iterrows():
    company = row["company"]
    raw = clean_json_text(row["fit_brief_json"])

    try:
        parsed = parse_first_json_object(raw)
        scores = parsed.get("scores", {})

        summary_rows.append({
            "company": company,
            "thesis_fit_score": extract_score(scores, "thesis_fit_score"),
            "pmf_scale_score": extract_score(scores, "pmf_scale_score"),
            "evidence_confidence_score": (
                extract_score(scores, "evidence_confidence_score")
                or extract_score(scores, "overall_confidence")
            ),
            "katelynd_role_fit_score": extract_score(scores, "katelynd_role_fit_score"),
            "operator_timing_score": extract_score(scores, "operator_timing_score"),
            "final_recommendation": parsed.get("final_recommendation"),
            "priority_level": parsed.get("priority_level"),
            "business_model_classification": parsed.get("business_model_classification"),
            "commercial_scale_assessment": parsed.get("commercial_scale_assessment"),
            "final_takeaway": parsed.get("final_takeaway"),
            "commercial_scale_finding": row.get("commercial_scale_finding", "")
        })

    except Exception as e:
        summary_rows.append({
            "company": company,
            "error": f"Could not parse JSON: {e}",
            "raw_preview": raw[:500],
            "commercial_scale_finding": row.get("commercial_scale_finding", "")
        })

summary_df = pd.DataFrame(summary_rows)

# -----------------------------
# Normalize nested text fields
# -----------------------------

for col in ["commercial_scale_assessment", "final_takeaway"]:
    if col in summary_df.columns:
        summary_df[col] = summary_df[col].apply(normalize_jsonish)

# -----------------------------
# Convert scores to numeric
# -----------------------------

score_cols = [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]

for col in score_cols:
    if col in summary_df.columns:
        summary_df[col] = pd.to_numeric(summary_df[col], errors="coerce")

# -----------------------------
# Parse warning
# -----------------------------

if "error" in summary_df.columns and summary_df["error"].notna().any():
    print("WARNING: Some rows could not be parsed.")
    display(summary_df[summary_df["error"].notna()])

# -----------------------------
# Required summary columns check
# -----------------------------

required_summary_cols = [
    "company",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "priority_level",
    "business_model_classification",
    "commercial_scale_assessment",
    "commercial_scale_finding"
]

missing_summary_cols = [col for col in required_summary_cols if col not in summary_df.columns]

if missing_summary_cols:
    raise ValueError(f"STOP: summary_df missing required columns: {missing_summary_cols}")

# -----------------------------
# Calibration flags
# -----------------------------

summary_df["calibration_flag"] = summary_df.apply(build_calibration_flag, axis=1)

# -----------------------------
# Display summary
# -----------------------------

display_cols = [
    "company",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "priority_level",
    "business_model_classification",
    "commercial_scale_assessment",
    "calibration_flag"
]

display_cols = [col for col in display_cols if col in summary_df.columns]

summary_df[display_cols]

# =============================================================================

# STEP 10A - Deterministic priority adjudication

# =============================================================================

# Purpose:

# - Enforce hard priority rules after LLM scoring

# - Prevent role fit / thesis interest from incorrectly promoting weak-scale companies

# - Update fit_brief_json, checkpoint, and archive rows in place

# =============================================================================
# STEP 10A - Deterministic priority adjudication
# =============================================================================
# Purpose:
# - Enforce hard priority rules after LLM scoring
# - Use native P0/P1/P2/P3/P4 priority labels
# - Prevent role fit / thesis interest from incorrectly promoting weak-scale companies
# - Treat incorrect outputs as decision-logic calibration data
# - Update fit_brief_json in df, checkpoint, and current batch raw/archive rows
#
# Required flow:
# 1. Run Step 10
# 2. Run this Step 10A cell
# 3. Rerun Step 10
# 4. Run Step 10B

import json
import re
import pandas as pd
import shutil
from pathlib import Path

# -----------------------------
# Safety checks
# -----------------------------

if "df" not in globals() or not isinstance(df, pd.DataFrame) or df.empty:
    raise NameError("STOP: df is not available or empty.")

if "BATCH_NAME" not in globals():
    raise NameError("STOP: BATCH_NAME is not defined.")

if "batch_checkpoint_path" not in globals() or "drive_checkpoint_path" not in globals():
    raise NameError("STOP: checkpoint paths are not defined.")

required_current_schema_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

missing_cols = [col for col in required_current_schema_cols if col not in df.columns]

if missing_cols:
    raise ValueError(f"STOP: df missing required columns: {missing_cols}")

# -----------------------------
# JSON helpers
# -----------------------------

def clean_json_text(text):
    text = str(text).strip()
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()

def parse_first_json_object(text):
    raw = clean_json_text(text)
    start = raw.find("{")

    if start == -1:
        raise ValueError("No JSON object found")

    decoder = json.JSONDecoder()
    parsed, end = decoder.raw_decode(raw[start:])
    return parsed

def get_score(parsed, key):
    scores = parsed.get("scores", {})
    value = scores.get(key)

    if isinstance(value, dict):
        return value.get("score")

    return value

def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default

def normalize_signal(value):
    text = str(value).strip().lower()

    if text in ["strong", "moderate", "weak", "none"]:
        return text

    if "strong" in text:
        return "strong"
    if "moderate" in text or "medium" in text:
        return "moderate"
    if "weak" in text:
        return "weak"
    if "none" in text or text in ["no", "n/a", "na", ""]:
        return "none"

    return "none"

def text_contains_any(text, terms):
    text = str(text).lower()
    return any(term.lower() in text for term in terms)

def bool_from_value(value, default=False):
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in ["true", "yes", "1"]:
        return True

    if text in ["false", "no", "0"]:
        return False

    return default

def append_flag(existing, new_flag):
    existing = str(existing or "").strip()

    if not existing:
        return new_flag

    if new_flag in existing:
        return existing

    return existing + " | " + new_flag

def priority_code(value):
    text = str(value or "").upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def normalize_priority_label(value):
    text = str(value or "").strip()
    lower = text.lower()

    if lower.startswith("p0") or "highest-priority" in lower or "highest priority" in lower:
        return "P0: Highest-priority target"

    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or "near-priority" in lower
        or "near priority" in lower
        or "p1-border" in lower
        or "p1 border" in lower
        or "strong p2" in lower
    ):
        return "P1: Near-priority target"

    # Backward compatibility: old P1 means new P0.
    if lower.startswith("p1: high-priority") or lower.startswith("p1: high priority"):
        return "P0: Highest-priority target"

    if lower.startswith("p2") or "review p2" in lower or "worth deeper diligence" in lower:
        return "P2: Worth deeper diligence"

    if lower.startswith("p3") or "watch list" in lower or "watchlist" in lower:
        return "P3: Watch list"

    if lower.startswith("p4") or "low priority" in lower or "likely reject" in lower or "reject" in lower:
        return "P4: Low priority / likely reject"

    return text

def recommendation_for_priority(priority_level):
    code = priority_code(priority_level)

    return {
        "P0": "Strong fit, active pursuit",
        "P1": "Strong fit, near-priority diligence",
        "P2": "Possible fit, pending diligence",
        "P3": "Watch list",
        "P4": "Weak fit"
    }.get(code, "Watch list")

# -----------------------------
# Signal inference helpers
# -----------------------------

def get_scale_assessment(parsed):
    scale_assessment = parsed.get("scale_signal_assessment", {})

    if isinstance(scale_assessment, dict):
        return scale_assessment

    return {}

def infer_commercial_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("commercial_scale_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("commercial_scale_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("commercial_scale_finding", "")),
        str(parsed.get("commercial_scale_assessment", "")),
        str(parsed.get("pmf_scale_assessment", "")),
    ]).lower()

    weak_markers = [
        "weak public commercial",
        "weak commercial",
        "no strong public commercial",
        "no strong public commercial scale",
        "no credible public arr",
        "no public arr",
        "no company-reported arr",
        "no company-reported revenue",
        "no credible third-party revenue",
        "no credible third-party revenue estimate",
        "not well evidenced",
        "unproven publicly",
        "commercial traction remains unsubstantiated",
        "does not yet establish strong revenue quality",
        "pricing exists, but commercial traction remains unsubstantiated"
    ]

    strong_markers = [
        "strong commercial",
        "$100m",
        "$1b",
        "$500m",
        "100m revenue",
        "100m arr",
        "1b arr",
        "500m/year",
        "paid-member scale",
        "paid-user scale",
        "paying members",
        "paying subscribers",
        "subscribers",
        "first-year renewal",
        "substantial paid-user scale",
        "meaningful paid-customer scale",
        "credible estimated revenue",
        "estimated revenue",
        "revenue run-rate",
        "arr"
    ]

    moderate_markers = [
        "moderate commercial",
        "moderately evidenced",
        "paid pricing",
        "subscription model",
        "membership model",
        "test-kit",
        "consumer usage",
        "pricing and product signals",
        "visible pricing",
        "real business model"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

def infer_institutional_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("institutional_distribution_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("institutional_distribution_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("payer_institutional_finding", "")),
        str(parsed.get("pmf_scale_assessment", "")),
        str(parsed.get("business_model_classification", "")),
    ]).lower()

    weak_markers = [
        "no strong public institutional",
        "no strong institutional signal",
        "mostly d2c",
        "mostly d2c/cash-pay",
        "no public payer contracts",
        "no clear payer contracts",
        "no medicare",
        "no medicaid",
        "not broad payer",
        "not broad institutional",
        "does not surface clear payer contracts",
        "no clear evidence of payer contracts"
    ]

    strong_markers = [
        "strong institutional",
        "top health plans",
        "health plans and employers",
        "employer/health-plan",
        "employers/health plans",
        "covered lives",
        "health-plan channels",
        "enterprise clients",
        "employer customers",
        "lives covered",
        "payer contracts",
        "provider network",
        "health system"
    ]

    moderate_markers = [
        "some institutional",
        "limited partner",
        "employer-facing",
        "provider-facing",
        "b2b2c",
        "partnership",
        "employer page",
        "provider referral",
        "benefits-consultant",
        "one named plan partnership",
        "emerging payer-linked distribution"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

def infer_outcomes_signal(row, parsed):
    scale_assessment = get_scale_assessment(parsed)
    explicit = normalize_signal(scale_assessment.get("outcomes_signal", ""))

    if explicit in ["strong", "moderate", "weak", "none"] and str(scale_assessment.get("outcomes_signal", "")).strip():
        return explicit

    text = " ".join([
        str(row.get("outcomes_finding", "")),
        str(parsed.get("pmf_scale_assessment", "")),
    ]).lower()

    weak_markers = [
        "no strong public outcomes",
        "no peer-reviewed",
        "no clinical trials",
        "not a clinical trial",
        "no control group",
        "mostly marketing",
        "limited public evidence",
        "no meaningful outcomes",
        "not independently validated outcomes"
    ]

    strong_markers = [
        "randomized controlled trial",
        "nature medicine",
        "peer-reviewed",
        "published real-world evidence",
        "claims-based study",
        "clinical efficacy",
        "real-world evidence",
        "health improvement",
        "reduced costs",
        "improved outcomes"
    ]

    moderate_markers = [
        "mixed",
        "weak-to-moderate",
        "moderate evidence",
        "company-reported",
        "retrospective",
        "engagement-linked",
        "validation studies",
        "measurement studies",
        "behavior-change"
    ]

    if text_contains_any(text, weak_markers):
        return "weak"

    if text_contains_any(text, strong_markers):
        return "strong"

    if text_contains_any(text, moderate_markers):
        return "moderate"

    return "none"

# -----------------------------
# Deterministic adjudication logic
# -----------------------------

adjudication_rows = []

for idx, row in df.iterrows():
    company = str(row["company"]).strip()
    parsed = parse_first_json_object(row["fit_brief_json"])

    thesis = safe_int(get_score(parsed, "thesis_fit_score"))
    pmf = safe_int(get_score(parsed, "pmf_scale_score"))
    evidence = safe_int(get_score(parsed, "evidence_confidence_score"))
    role_fit = safe_int(get_score(parsed, "katelynd_role_fit_score"))
    timing = safe_int(get_score(parsed, "operator_timing_score"))

    scale_assessment = get_scale_assessment(parsed)

    commercial_signal = infer_commercial_signal(row, parsed)
    institutional_signal = infer_institutional_signal(row, parsed)
    outcomes_signal = infer_outcomes_signal(row, parsed)

    plausible_near_term_scale_path = bool_from_value(
        scale_assessment.get("plausible_near_term_scale_path"),
        default=False
    )

    if not plausible_near_term_scale_path:
        plausible_near_term_scale_path = (
            commercial_signal == "strong" or
            institutional_signal == "strong" or
            (
                outcomes_signal == "strong" and
                (
                    commercial_signal in ["moderate", "strong"] or
                    institutional_signal in ["moderate", "strong"]
                )
            )
        )

    commercial_strong_gate = commercial_signal == "strong" and evidence >= 50
    institutional_strong_gate = institutional_signal == "strong" and evidence >= 50

    outcomes_plus_scale_path_gate = (
        outcomes_signal == "strong" and
        plausible_near_term_scale_path is True and
        evidence >= 55 and
        pmf >= 70 and
        (
            commercial_signal in ["moderate", "strong"] or
            institutional_signal in ["moderate", "strong"]
        )
    )

    score_qualifies_for_p2 = pmf >= 70 and evidence >= 50

    qualifies_for_p2 = (
        score_qualifies_for_p2 or
        commercial_strong_gate or
        institutional_strong_gate or
        outcomes_plus_scale_path_gate
    )

    strong_signal_count = sum([
        commercial_signal == "strong",
        institutional_signal == "strong",
        outcomes_signal == "strong"
    ])

    moderate_or_strong_signal_count = sum([
        commercial_signal in ["moderate", "strong"],
        institutional_signal in ["moderate", "strong"],
        outcomes_signal in ["moderate", "strong"]
    ])

    qualifies_for_p1 = (
        qualifies_for_p2 and
        thesis >= 85 and
        pmf >= 74 and
        evidence >= 55 and
        role_fit >= 78 and
        timing >= 72 and
        (
            strong_signal_count >= 1 or
            moderate_or_strong_signal_count >= 2
        )
    )

    qualifies_for_p0 = (
        qualifies_for_p1 and
        thesis >= 88 and
        pmf >= 82 and
        evidence >= 75 and
        role_fit >= 80 and
        timing >= 78 and
        (
            strong_signal_count >= 3 or
            (
                institutional_signal == "strong" and
                outcomes_signal in ["moderate", "strong"] and
                commercial_signal in ["moderate", "strong"]
            ) or
            (
                commercial_signal == "strong" and
                institutional_signal == "strong"
            )
        )
    )


    qualifies_for_p4 = (
        not qualifies_for_p2 and
        (
            thesis < 55 or
            pmf < 45 or
            role_fit < 55 or
            timing < 55
        ) and
        commercial_signal in ["weak", "none"] and
        institutional_signal in ["weak", "none"]
    )

    original_priority = normalize_priority_label(parsed.get("priority_level", ""))
    original_flag = str(parsed.get("calibration_flag", "") or "").strip()

    if qualifies_for_p0:
        adjudicated_priority = "P0: Highest-priority target"
        adjudication_action = "assigned_P0"

    elif qualifies_for_p1:
        adjudicated_priority = "P1: Near-priority target"
        adjudication_action = "assigned_P1"

    elif qualifies_for_p2:
        adjudicated_priority = "P2: Worth deeper diligence"
        adjudication_action = "assigned_P2"

    elif qualifies_for_p4:
        adjudicated_priority = "P4: Low priority / likely reject"
        adjudication_action = "assigned_P4"

    else:
        adjudicated_priority = "P3: Watch list"
        adjudication_action = "assigned_P3"

    adjudicated_recommendation = recommendation_for_priority(adjudicated_priority)
    adjudicated_flag = original_flag

    if original_priority != "" and original_priority != adjudicated_priority:
        adjudicated_flag = append_flag(
            adjudicated_flag,
            f"Deterministic gate: reassigned from {original_priority} to {adjudicated_priority}."
        )

    if adjudicated_priority.startswith("P1"):
        adjudicated_flag = append_flag(
            adjudicated_flag,
            "Deterministic gate: P1 indicates near-priority / former P1-border; validate before active pursuit."
        )

    if adjudicated_priority.startswith("P2") and (evidence < 65 or pmf < 70):
        adjudicated_flag = append_flag(
            adjudicated_flag,
            "Deterministic gate: P2 has moderate evidence and/or PMF; diligence required."
        )

    parsed["priority_adjudication"] = {
        "decision_logic_version": "p0_p4_scale_engine_gate_v2",
        "commercial_scale_signal": commercial_signal,
        "institutional_distribution_signal": institutional_signal,
        "outcomes_signal": outcomes_signal,
        "plausible_near_term_scale_path": plausible_near_term_scale_path,
        "strong_signal_count": strong_signal_count,
        "moderate_or_strong_signal_count": moderate_or_strong_signal_count,
        "score_qualifies_for_p2": score_qualifies_for_p2,
        "commercial_strong_gate": commercial_strong_gate,
        "institutional_strong_gate": institutional_strong_gate,
        "outcomes_plus_scale_path_gate": outcomes_plus_scale_path_gate,
        "qualifies_for_p2": qualifies_for_p2,
        "qualifies_for_p1": qualifies_for_p1,
        "qualifies_for_p0": qualifies_for_p0,
        "qualifies_for_p4": qualifies_for_p4,
        "original_priority_level": original_priority,
        "adjudicated_priority_level": adjudicated_priority,
        "adjudication_action": adjudication_action
    }

    parsed["priority_level"] = adjudicated_priority
    parsed["final_recommendation"] = adjudicated_recommendation
    parsed["calibration_flag"] = adjudicated_flag

    if adjudicated_priority.startswith("P3"):
        parsed["final_takeaway"] = (
            f"{company} remains strategically interesting, but the current public evidence does not clear the P2 priority gate. "
            "Keep on watch list until stronger commercial traction, institutional distribution, or outcomes-plus-scale evidence emerges."
        )

    elif adjudicated_priority.startswith("P4"):
        parsed["final_takeaway"] = (
            f"{company} does not currently clear the job-search priority gate based on available evidence. "
            "Revisit only if stronger scale, outcomes, or role-fit evidence emerges."
        )

    df.loc[idx, "fit_brief_json"] = json.dumps(parsed, indent=2, ensure_ascii=False)

    adjudication_rows.append({
        "company": company,
        "thesis_fit_score": thesis,
        "pmf_scale_score": pmf,
        "evidence_confidence_score": evidence,
        "katelynd_role_fit_score": role_fit,
        "operator_timing_score": timing,
        "commercial_scale_signal": commercial_signal,
        "institutional_distribution_signal": institutional_signal,
        "outcomes_signal": outcomes_signal,
        "plausible_near_term_scale_path": plausible_near_term_scale_path,
        "strong_signal_count": strong_signal_count,
        "moderate_or_strong_signal_count": moderate_or_strong_signal_count,
        "score_qualifies_for_p2": score_qualifies_for_p2,
        "commercial_strong_gate": commercial_strong_gate,
        "institutional_strong_gate": institutional_strong_gate,
        "outcomes_plus_scale_path_gate": outcomes_plus_scale_path_gate,
        "qualifies_for_p2": qualifies_for_p2,
        "qualifies_for_p1": qualifies_for_p1,
        "qualifies_for_p0": qualifies_for_p0,
        "qualifies_for_p4": qualifies_for_p4,
        "original_priority": original_priority,
        "adjudicated_priority": adjudicated_priority,
        "adjudication_action": adjudication_action
    })

adjudication_df = pd.DataFrame(adjudication_rows)

# -----------------------------
# Save corrected checkpoint
# -----------------------------

df = df[required_current_schema_cols].copy().reset_index(drop=True)
checkpoint_df = df.copy()

Path(batch_checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
df.to_csv(batch_checkpoint_path, index=False)

Path(drive_checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
shutil.copy(batch_checkpoint_path, drive_checkpoint_path)

print("PASS: Deterministic priority adjudication applied.")
print("Local checkpoint:", batch_checkpoint_path)
print("Drive checkpoint:", drive_checkpoint_path)

print("\nAdjudication summary:")
display(adjudication_df)

# -----------------------------
# Update already-written raw/archive rows in place
# -----------------------------

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"
local_batches_folder = Path("research_batches")

archive_paths = [
    Path("health_tech_raw_research_ARCHIVE.csv"),
    drive_folder / "health_tech_raw_research_ARCHIVE.csv"
]

archive_paths.extend(sorted(local_batches_folder.glob(f"{BATCH_NAME}_raw_*.csv")))
archive_paths.extend(sorted(drive_batches_folder.glob(f"{BATCH_NAME}_raw_*.csv")))

updated_files = []

for archive_path in archive_paths:
    archive_path = Path(archive_path)

    if not archive_path.exists():
        continue

    archive_df = pd.read_csv(archive_path)

    if "batch_name" not in archive_df.columns or "company" not in archive_df.columns:
        continue

    batch_mask = archive_df["batch_name"].astype(str).eq(BATCH_NAME)

    if not batch_mask.any():
        continue

    for _, source_row in df.iterrows():
        company = source_row["company"]
        row_mask = batch_mask & archive_df["company"].astype(str).eq(company)

        if not row_mask.any():
            continue

        for col in required_current_schema_cols:
            if col in archive_df.columns:
                archive_df.loc[row_mask, col] = source_row[col]

    archive_df.to_csv(archive_path, index=False)
    updated_files.append(str(archive_path))

print("\nUpdated archive/current-batch files:")
for path in updated_files:
    print("-", path)

print("\nNext: rerun Step 10, then Step 10B.")


# =============================================================================

# STEP 10B - Batch QA checks before export/master update

# =============================================================================

# 10B - Batch QA checks before export / master update
# Purpose:
# - Check current batch raw fields
# - Check obvious wrong-company contamination
# - Surface priority/evidence calibration issues
# - Use narrower D2C detection so hybrid B2B2C/payer/employer companies are not incorrectly flagged as D2C

import pandas as pd

print("Running batch QA checks...")
print("df shape:", df.shape)
print("companies:", df["company"].tolist())

qa_flags = []

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def is_d2c_specific_business_model(business_model_text):
    """
    Detects true D2C / cash-pay companies without over-flagging
    hybrid payer/employer/provider-enabled consumer platforms.
    """
    business_model = safe_text(business_model_text).lower()

    institutional_terms = [
        "b2b2c",
        "payer",
        "employer",
        "provider",
        "benefits",
        "insurance",
        "health plan",
        "government",
        "pharma",
        "medicaid",
        "medicare"
    ]

    has_institutional_path = any(term in business_model for term in institutional_terms)

    appears_d2c = (
        "d2c" in business_model
        or "cash-pay" in business_model
        or "cash pay" in business_model
        or "primarily d2c" in business_model
        or "primarily cash" in business_model
    )

    # Do not treat generic "consumer health platform" as D2C if the classification
    # is clearly hybrid/B2B2C/payer/employer/provider-enabled.
    d2c_specific_review_needed = appears_d2c and not (
        has_institutional_path and "hybrid" in business_model
    )

    return d2c_specific_review_needed

def commercial_signal_is_weak(commercial_text):
    text = safe_text(commercial_text).lower()

    weak_phrases = [
        "no strong public commercial scale evidence found",
        "weak evidence",
        "commercial scale evidence is weak",
        "weak-to-moderate",
        "not enough hard evidence",
        "not strongly substantiated",
        "not revenue quality",
        "no credible public revenue",
        "no public revenue",
        "no verified current arr",
        "no public arr",
        "no subscriber count",
        "no retention",
        "no renewal",
        "no cac",
        "no margin"
    ]

    if text == "":
        return True

    return any(phrase in text for phrase in weak_phrases)

def add_flag(company, issue):
    qa_flags.append({
        "company": company,
        "issue": issue
    })

# -----------------------------
# 1. Check for blank raw research fields
# -----------------------------

raw_fields = [
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

missing_raw_fields = [field for field in raw_fields if field not in df.columns]

if missing_raw_fields:
    for field in missing_raw_fields:
        add_flag("BATCH", f"Missing raw field column: {field}")
else:
    for _, row in df.iterrows():
        company = row["company"]

        for field in raw_fields:
            value = row.get(field, "")

            if pd.isna(value) or str(value).strip() == "":
                add_flag(company, f"Blank field: {field}")

# -----------------------------
# 2. Check for likely wrong-company contamination
# -----------------------------

suspicious_terms = [
    "wealth management",
    "edtech",
    "unrelated",
    "different company"
]

for _, row in df.iterrows():
    company = row["company"]

    combined_text = " ".join([
        str(row.get("funding_finding", "")),
        str(row.get("payer_institutional_finding", "")),
        str(row.get("outcomes_finding", "")),
        str(row.get("commercial_scale_finding", "")),
        str(row.get("fit_brief_json", ""))
    ]).lower()

    for term in suspicious_terms:
        if term in combined_text:
            add_flag(company, f"Possible wrong-company contamination: '{term}'")

# -----------------------------
# 3. Check P2s with moderate/weak evidence
# -----------------------------

if "summary_df" in globals():
    for _, row in summary_df.iterrows():
        company = row["company"]
        priority = safe_text(row.get("priority_level"))
        evidence = row.get("evidence_confidence_score", 0)
        pmf = row.get("pmf_scale_score", 0)

        if priority == "P2: Worth deeper diligence" and (evidence < 65 or pmf < 70):
            add_flag(company, "Review P2: moderate evidence and/or PMF")

# -----------------------------
# 4. D2C commercial-scale sanity check
# -----------------------------

if "summary_df" in globals():
    for _, row in summary_df.iterrows():
        company = row["company"]
        business_model = row.get("business_model_classification", "")
        priority = safe_text(row.get("priority_level"))
        evidence = row.get("evidence_confidence_score", 0)
        pmf = row.get("pmf_scale_score", 0)

        raw_match = df[df["company"] == company]

        if not raw_match.empty:
            commercial_text = str(raw_match.iloc[0].get("commercial_scale_finding", ""))
        else:
            commercial_text = ""

        d2c_specific_review_needed = is_d2c_specific_business_model(business_model)
        weak_commercial_signal = commercial_signal_is_weak(commercial_text)

        if (
            d2c_specific_review_needed
            and priority in ["P1: High-priority target", "P2: Worth deeper diligence"]
            and weak_commercial_signal
        ):
            add_flag(company, "Review D2C priority: weak commercial-scale evidence")

        if (
            d2c_specific_review_needed
            and pmf >= 75
            and evidence < 60
        ):
            add_flag(company, "Review D2C scale claim: strong PMF score but moderate/weak evidence confidence")

# -----------------------------
# 5. Surface calibration flags from Step 10
# -----------------------------

if "summary_df" in globals() and "calibration_flag" in summary_df.columns:
    flagged_rows = summary_df[
        summary_df["calibration_flag"].notna()
        & (summary_df["calibration_flag"].astype(str).str.strip() != "")
    ]

    for _, row in flagged_rows.iterrows():
        add_flag(row["company"], f"Calibration flag: {row['calibration_flag']}")

# -----------------------------
# 6. Dedupe QA flags
# -----------------------------

qa_df = pd.DataFrame(qa_flags)

if not qa_df.empty:
    qa_df = qa_df.drop_duplicates().reset_index(drop=True)

if qa_df.empty:
    print("QA passed. No issues flagged.")
else:
    print("QA flags found. Review before updating master.")
    display(qa_df)

# =============================================================================

# STEP 11 - Export current batch only

# =============================================================================

# Step 11 - Export current batch only
# Purpose:
# - Export raw current-batch research
# - Export parsed current-batch summary
# - Confirm commercial-scale fields are included

print("Exporting CURRENT BATCH ONLY.")
print("Raw df shape:", df.shape)
print("Summary df shape:", summary_df.shape)

required_raw_export_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json"
]

required_summary_export_cols = [
    "company",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "priority_level",
    "business_model_classification",
    "commercial_scale_assessment",
    "commercial_scale_finding",
    "calibration_flag"
]

missing_raw_cols = [col for col in required_raw_export_cols if col not in df.columns]
missing_summary_cols = [col for col in required_summary_export_cols if col not in summary_df.columns]

if missing_raw_cols:
    raise ValueError(f"STOP: Raw df missing export columns: {missing_raw_cols}")

if missing_summary_cols:
    raise ValueError(f"STOP: summary_df missing export columns: {missing_summary_cols}")

df.to_csv(batch_raw_export_path, index=False)
summary_df.to_csv(batch_summary_export_path, index=False)

print("Saved batch raw export to:")
print(batch_raw_export_path)

print("Saved batch summary export to:")
print(batch_summary_export_path)

print("\nCommercial-scale fields confirmed in exports:")
print("- df includes commercial_scale_finding")
print("- summary_df includes commercial_scale_finding and commercial_scale_assessment")

# =============================================================================

# STEP 11A - Final raw archive QA

# =============================================================================

# 11A - Final raw archive QA
# Purpose:
# - Confirm raw archive exists and is structurally clean
# - Confirm core raw fields are complete
# - Confirm fit_brief_json parses
# - Confirm no duplicate company+batch records
# - Support commercial_scale_finding while staying backward-compatible with older archived rows

import pandas as pd
import json
from pathlib import Path
from google.colab import drive
import shutil

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_archive_path = drive_folder / "health_tech_raw_research_ARCHIVE.csv"
local_archive_path = Path("health_tech_raw_research_ARCHIVE.csv")

if not drive_archive_path.exists():
    raise FileNotFoundError(f"Archive not found in Drive: {drive_archive_path}")

shutil.copy(drive_archive_path, local_archive_path)

archive_df = pd.read_csv(local_archive_path)

# -----------------------------
# Required columns
# -----------------------------

core_required_cols = [
    "company",
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "fit_brief_json",
    "batch_name",
    "archive_saved_at",
    "archive_record_id"
]

# New field added during commercial-scale upgrade.
# Older archived rows may be blank, but all new rows should have it.
commercial_scale_col = "commercial_scale_finding"

all_expected_cols = core_required_cols + [commercial_scale_col]

print("ARCHIVE SHAPE:", archive_df.shape)
print("COMPANY COUNT:", archive_df["company"].nunique())

missing_core_cols = [col for col in core_required_cols if col not in archive_df.columns]
missing_expected_cols = [col for col in all_expected_cols if col not in archive_df.columns]

print("MISSING CORE COLUMNS:", missing_core_cols)
print("MISSING EXPECTED COLUMNS:", missing_expected_cols)

if missing_core_cols:
    raise ValueError(f"STOP: Archive is missing core required columns: {missing_core_cols}")

# Backward-compatible schema repair in memory only.
# This does not save the archive; it just allows QA to run cleanly.
if commercial_scale_col not in archive_df.columns:
    archive_df[commercial_scale_col] = ""
    print("NOTE: commercial_scale_finding column was missing and added in memory for QA compatibility.")

# -----------------------------
# Blank-field check: core fields
# -----------------------------

blank_issues = []

for col in core_required_cols:
    blank_mask = archive_df[col].isna() | (archive_df[col].astype(str).str.strip() == "")
    for company in archive_df.loc[blank_mask, "company"].tolist():
        blank_issues.append({
            "company": company,
            "blank_field": col,
            "severity": "FAIL"
        })

blank_df = pd.DataFrame(blank_issues)

if blank_df.empty:
    print("CORE BLANK FIELD CHECK: PASS")
else:
    print("CORE BLANK FIELD CHECK: FAIL")
    display(blank_df)

# -----------------------------
# Commercial-scale field check
# -----------------------------
# Older rows may have blank commercial_scale_finding because the field did not exist yet.
# New rows should not be blank.
#
# Rule:
# - If the column exists and is populated for a batch, good.
# - If a batch has blanks in commercial_scale_finding, flag as WARNING, not FAIL.
# - Future new batches should be enforced by Step 8A before archiving.

commercial_blank_mask = (
    archive_df[commercial_scale_col].isna()
    | (archive_df[commercial_scale_col].astype(str).str.strip() == "")
)

commercial_blank_df = archive_df.loc[
    commercial_blank_mask,
    ["company", "batch_name", "date_researched"]
].copy()

if commercial_blank_df.empty:
    print("COMMERCIAL SCALE FIELD CHECK: PASS")
else:
    print("COMMERCIAL SCALE FIELD CHECK: WARNING")
    print(
        "Some archived rows have blank commercial_scale_finding. "
        "This is expected for older research batches created before the commercial-scale field was added. "
        "New batches should not have blanks because Step 8A now blocks them."
    )
    display(commercial_blank_df)

# -----------------------------
# Validate fit_brief_json parses
# -----------------------------

json_issues = []

for _, row in archive_df.iterrows():
    try:
        json.loads(str(row["fit_brief_json"]))
    except Exception as e:
        json_issues.append({
            "company": row["company"],
            "batch_name": row.get("batch_name", ""),
            "json_issue": str(e)
        })

json_issue_df = pd.DataFrame(json_issues)

if json_issue_df.empty:
    print("JSON PARSE CHECK: PASS")
else:
    print("JSON PARSE CHECK: FAIL")
    display(json_issue_df)

# -----------------------------
# Duplicate company+batch check
# -----------------------------

duplicate_df = archive_df[
    archive_df.duplicated(subset=["company", "batch_name"], keep=False)
]

if duplicate_df.empty:
    print("DUPLICATE COMPANY+BATCH CHECK: PASS")
else:
    print("DUPLICATE COMPANY+BATCH CHECK: FAIL")
    display(duplicate_df[["company", "batch_name", "archive_saved_at"]])

# -----------------------------
# Batch summary
# -----------------------------

print("\nBATCH SUMMARY:")
display(
    archive_df
    .groupby("batch_name")
    .agg(
        company_count=("company", "nunique"),
        row_count=("company", "count"),
        commercial_scale_populated=(
            commercial_scale_col,
            lambda x: x.notna().sum() - (x.astype(str).str.strip() == "").sum()
        )
    )
    .reset_index()
)

print("\nALL ARCHIVED COMPANIES:")
display(
    archive_df[
        [
            "company",
            "batch_name",
            "date_researched",
            commercial_scale_col
        ]
    ]
    .sort_values(["batch_name", "company"])
)

# -----------------------------
# Final pass/fail gate
# -----------------------------

has_core_blank_fail = not blank_df.empty
has_json_fail = not json_issue_df.empty
has_duplicate_fail = not duplicate_df.empty

if has_core_blank_fail or has_json_fail or has_duplicate_fail:
    raise ValueError(
        "11A archive QA failed. Review failed checks above before continuing."
    )

print("\n11A raw archive QA complete.")
print("PASS: Core archive checks passed.")
print("NOTE: commercial_scale_finding blanks are warnings for older archived rows only.")

# =============================================================================

# STEP 12 - Add/update current batch in master

# =============================================================================

# 12 - Add current batch to master as review-needed
# Purpose:
# - Add/update the current batch summary_df into the active master
# - Preserve existing human-reviewed priority/status/notes for companies already in master
# - For brand-new companies, initialize reviewed_priority_level from model priority_level
# - Mark brand-new companies as "New batch - needs review"
# - Backup active master before saving
# - Save updated master locally + to Google Drive
# - Includes commercial_scale_finding and commercial_scale_assessment

import pandas as pd
import numpy as np
import shutil
from pathlib import Path
from datetime import datetime
from google.colab import drive, files

# -----------------------------
# Config
# -----------------------------

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_folder.mkdir(parents=True, exist_ok=True)

MASTER_FILENAME = "health_tech_market_research_summary_MASTER.csv"
drive_master_path = drive_folder / MASTER_FILENAME
local_master_path = Path(MASTER_FILENAME)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

backup_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_backup_before_12_{timestamp}.csv"
updated_snapshot_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_after_12_{timestamp}.csv"
change_log_drive_path = drive_folder / f"health_tech_market_research_summary_MASTER_12_change_log_{timestamp}.csv"

# Try to capture batch name if your notebook has one
if "BATCH_NAME" in globals():
    batch_label = str(BATCH_NAME)
elif "batch_name" in globals():
    batch_label = str(batch_name)
elif "RUN_ID" in globals():
    batch_label = str(RUN_ID)
else:
    batch_label = f"unknown_batch_{timestamp}"

# -----------------------------
# Safety checks
# -----------------------------

if "summary_df" not in globals():
    raise NameError(
        "STOP: summary_df is not defined. Run Step 10 before Step 12."
    )

if not isinstance(summary_df, pd.DataFrame):
    raise TypeError("STOP: summary_df exists but is not a pandas DataFrame.")

if summary_df.empty:
    raise ValueError("STOP: summary_df is empty. Do not update master.")

required_summary_cols = [
    "company",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "priority_level",
    "business_model_classification",
    "commercial_scale_finding",
    "commercial_scale_assessment",
    "calibration_flag"
]

missing_summary_cols = [col for col in required_summary_cols if col not in summary_df.columns]

if missing_summary_cols:
    raise ValueError(f"STOP: summary_df is missing required columns: {missing_summary_cols}")

if summary_df["company"].duplicated().any():
    dupes = summary_df[summary_df["company"].duplicated(keep=False)]["company"].tolist()
    raise ValueError(f"STOP: Duplicate companies found in summary_df: {dupes}")

if not drive_master_path.exists():
    raise FileNotFoundError(
        f"STOP: Active master not found in Google Drive: {drive_master_path}. "
        "Restore or create the master before running Step 12."
    )

# Load master from Drive, not local, to avoid stale local files
shutil.copy(drive_master_path, local_master_path)
master_df = pd.read_csv(local_master_path)

if "company" not in master_df.columns:
    raise ValueError("STOP: Master is missing company column.")

if master_df["company"].duplicated().any():
    dupes = master_df[master_df["company"].duplicated(keep=False)]["company"].tolist()
    raise ValueError(f"STOP: Duplicate companies found in master: {dupes}")

print("Loaded active master from Drive.")
print("Master shape before:", master_df.shape)
print("Master company count before:", master_df["company"].nunique())
print()
print("Current batch shape:", summary_df.shape)
print("Current batch companies:", summary_df["company"].tolist())

# -----------------------------
# Prepare columns
# -----------------------------

review_cols = [
    "reviewed_priority_level",
    "review_status",
    "review_notes"
]

model_cols_to_update = [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "priority_level",
    "business_model_classification",
    "calibration_flag"
]

optional_model_cols = [
    "final_takeaway",
    "commercial_scale_finding",
    "commercial_scale_assessment"
]

for col in optional_model_cols:
    if col in summary_df.columns:
        model_cols_to_update.append(col)

# Ensure master has all necessary columns
for col in ["company"] + model_cols_to_update + review_cols:
    if col not in master_df.columns:
        master_df[col] = ""

# Ensure summary has review columns
batch_df = summary_df.copy()

for col in review_cols:
    if col not in batch_df.columns:
        batch_df[col] = ""

# Clean calibration flags
if "calibration_flag" in master_df.columns:
    master_df["calibration_flag"] = master_df["calibration_flag"].fillna("")

if "calibration_flag" in batch_df.columns:
    batch_df["calibration_flag"] = batch_df["calibration_flag"].fillna("")

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

# -----------------------------
# Backup before modifying
# -----------------------------

master_df.to_csv(local_master_path, index=False)
shutil.copy(local_master_path, backup_drive_path)

print("\nBackup saved before Step 12 update:")
print(backup_drive_path)

# -----------------------------
# Apply updates
# -----------------------------

master_before = master_df.copy()
existing_companies = set(master_df["company"].tolist())

change_log = []
rows_to_append = []

def log_change(company, field, old_value, new_value, change_type):
    if safe_text(old_value) != safe_text(new_value):
        change_log.append({
            "company": company,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "change_type": change_type,
            "batch_label": batch_label,
            "updated_at": timestamp
        })

for _, batch_row in batch_df.iterrows():
    company = batch_row["company"]

    if company in existing_companies:
        # Existing company: update model-generated fields only.
        # Preserve human-reviewed fields unless they are blank.
        idx = master_df.index[master_df["company"] == company].tolist()[0]

        for col in model_cols_to_update:
            if col in batch_df.columns:
                old_value = master_df.loc[idx, col]
                new_value = batch_row[col]
                log_change(company, col, old_value, new_value, "existing_company_model_field_update")
                master_df.loc[idx, col] = new_value

        # Preserve existing human-review columns.
        # If blank, initialize them gently from the current model output.
        if safe_text(master_df.loc[idx, "reviewed_priority_level"]) == "":
            new_reviewed_priority = safe_text(batch_row.get("priority_level"))
            log_change(
                company,
                "reviewed_priority_level",
                master_df.loc[idx, "reviewed_priority_level"],
                new_reviewed_priority,
                "existing_company_initialize_blank_review_field"
            )
            master_df.loc[idx, "reviewed_priority_level"] = new_reviewed_priority

        if safe_text(master_df.loc[idx, "review_status"]) == "":
            new_status = "Existing company - needs review"
            log_change(
                company,
                "review_status",
                master_df.loc[idx, "review_status"],
                new_status,
                "existing_company_initialize_blank_review_field"
            )
            master_df.loc[idx, "review_status"] = new_status

        if safe_text(master_df.loc[idx, "review_notes"]) == "":
            takeaway = safe_text(batch_row.get("final_takeaway"))
            if takeaway:
                new_note = f"Updated from {batch_label} on {timestamp}; needs human review. Model takeaway: {takeaway}"
            else:
                new_note = f"Updated from {batch_label} on {timestamp}; needs human review."

            log_change(
                company,
                "review_notes",
                master_df.loc[idx, "review_notes"],
                new_note,
                "existing_company_initialize_blank_review_field"
            )
            master_df.loc[idx, "review_notes"] = new_note

    else:
        # New company: append model fields and initialize human-review fields.
        new_row = {}

        # Preserve all master columns
        for col in master_df.columns:
            new_row[col] = ""

        new_row["company"] = company

        for col in model_cols_to_update:
            if col in batch_df.columns:
                new_row[col] = batch_row[col]

        model_priority = safe_text(batch_row.get("priority_level"))
        calibration_flag = safe_text(batch_row.get("calibration_flag"))
        takeaway = safe_text(batch_row.get("final_takeaway"))

        new_row["reviewed_priority_level"] = model_priority
        new_row["review_status"] = "New batch - needs review"

        review_note_parts = [
            f"Added from {batch_label} on {timestamp}; needs human review."
        ]

        if calibration_flag:
            review_note_parts.append(f"Calibration flag: {calibration_flag}.")

        if takeaway:
            review_note_parts.append(f"Model takeaway: {takeaway}")

        new_row["review_notes"] = " ".join(review_note_parts)

        rows_to_append.append(new_row)

        for col, new_value in new_row.items():
            if safe_text(new_value) != "":
                log_change(company, col, "", new_value, "new_company_added")

# Append new companies
if rows_to_append:
    master_df = pd.concat([master_df, pd.DataFrame(rows_to_append)], ignore_index=True)

# -----------------------------
# Validation
# -----------------------------

if master_df["company"].duplicated().any():
    dupes = master_df[master_df["company"].duplicated(keep=False)]["company"].tolist()
    raise ValueError(f"STOP: Duplicate companies created after update: {dupes}")

expected_company_count = master_before["company"].nunique() + len([
    c for c in batch_df["company"].tolist()
    if c not in existing_companies
])

actual_company_count = master_df["company"].nunique()

if actual_company_count != expected_company_count:
    raise ValueError(
        "STOP: Unexpected company count after update. "
        f"Expected {expected_company_count}, got {actual_company_count}."
    )

# Confirm all batch companies are now in master
missing_after_update = sorted(set(batch_df["company"].tolist()) - set(master_df["company"].tolist()))

if missing_after_update:
    raise ValueError(f"STOP: Batch companies missing from updated master: {missing_after_update}")

# Confirm commercial-scale fields populated for this batch in master
commercial_issues = []

for field in ["commercial_scale_finding", "commercial_scale_assessment"]:
    if field not in master_df.columns:
        commercial_issues.append({
            "company": "MASTER",
            "issue": f"Missing master column: {field}"
        })
    else:
        batch_rows = master_df[master_df["company"].isin(batch_df["company"].tolist())]
        blank_mask = batch_rows[field].isna() | (batch_rows[field].astype(str).str.strip() == "")
        for company in batch_rows.loc[blank_mask, "company"].tolist():
            commercial_issues.append({
                "company": company,
                "issue": f"Blank commercial-scale field after update: {field}"
            })

if commercial_issues:
    print("STOP: Commercial-scale fields were not correctly carried into the master.")
    display(pd.DataFrame(commercial_issues))
    raise ValueError("Commercial-scale master update validation failed.")

# Confirm human-reviewed fields are nonblank for batch companies
batch_master_rows = master_df[master_df["company"].isin(batch_df["company"].tolist())].copy()

blank_review_issues = []

for col in review_cols:
    blank_mask = batch_master_rows[col].isna() | (batch_master_rows[col].astype(str).str.strip() == "")
    for company in batch_master_rows.loc[blank_mask, "company"].tolist():
        blank_review_issues.append({
            "company": company,
            "blank_review_field": col
        })

if blank_review_issues:
    print("STOP: Some batch companies have blank review fields after update.")
    display(pd.DataFrame(blank_review_issues))
    raise ValueError("Blank review fields after Step 12 update.")

# -----------------------------
# Save updated master + change log
# -----------------------------

change_log_df = pd.DataFrame(change_log)

master_df.to_csv(local_master_path, index=False)

# Save active official master to Drive
shutil.copy(local_master_path, drive_master_path)

# Save timestamped snapshot to Drive
master_df.to_csv("health_tech_market_research_summary_MASTER_after_12.csv", index=False)
shutil.copy("health_tech_market_research_summary_MASTER_after_12.csv", updated_snapshot_drive_path)

# Save change log
local_change_log_path = Path(f"health_tech_market_research_summary_MASTER_12_change_log_{timestamp}.csv")
change_log_df.to_csv(local_change_log_path, index=False)
shutil.copy(local_change_log_path, change_log_drive_path)

print("\nStep 12 master update complete.")
print("Batch label:", batch_label)
print("Master shape after:", master_df.shape)
print("Master company count after:", master_df["company"].nunique())

print("\nActive master saved to:")
print(drive_master_path)

print("\nTimestamped updated master snapshot:")
print(updated_snapshot_drive_path)

print("\nStep 12 change log saved to:")
print(change_log_drive_path)

# -----------------------------
# Display outputs
# -----------------------------

new_companies_added = sorted([c for c in batch_df["company"].tolist() if c not in existing_companies])
existing_companies_updated = sorted([c for c in batch_df["company"].tolist() if c in existing_companies])

print("\nNew companies added:")
print(new_companies_added if new_companies_added else "None")

print("\nExisting companies updated:")
print(existing_companies_updated if existing_companies_updated else "None")

display_cols = [
    "company",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "business_model_classification",
    "commercial_scale_assessment",
    "commercial_scale_finding",
    "calibration_flag",
    "review_notes"
]

display_cols = [col for col in display_cols if col in master_df.columns]

print("\nBatch companies in updated master:")
display(
    master_df[
        master_df["company"].isin(batch_df["company"].tolist())
    ][display_cols].sort_values("company")
)

print("\nChange log preview:")
display(change_log_df)

print("\nReviewed priority summary after Step 12:")
display(
    master_df
    .groupby("reviewed_priority_level")
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values("company_count", ascending=False)
)

files.download(str(local_master_path))
files.download(str(local_change_log_path))

# =============================================================================

# =============================================================================
# STEP 12B - Priority field helper
# =============================================================================
# =============================================================================
# STEP 12B - Priority field helper
# =============================================================================
# Purpose:
# - Normalize old priority labels and new priority labels into clean P0-P4 dashboard priority
# - Keep priority_level as the automated/adjudicated system priority
# - Keep reviewed_priority_level as optional human override
# - Create final_priority_level for dashboard use
# - Create priority_source for transparency
# - Create final_priority_code / final_priority_rank for clean sorting
#
# New dashboard priority model:
# - P0 = highest-priority target / active pursuit
# - P1 = near-priority target / former P1-border
# - P2 = worth deeper diligence
# - P3 = watch list
# - P4 = low priority / likely reject

import pandas as pd
import re

# -----------------------------
# Basic helpers
# -----------------------------

def is_blank_value(value):
    return pd.isna(value) or str(value).strip() == ""

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def extract_priority_code(value):
    """
    Extract P0, P1, P2, P3, or P4 from a normalized or raw priority value.
    Handles new P0-P4 and older P1-P4 labels.
    """
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

# -----------------------------
# Priority normalization
# -----------------------------

def normalize_priority_level(value):
    """
    Converts old and new priority labels into clean dashboard labels.

    Old model:
    - P1: High-priority target              -> P0
    - Strong P2 / P1-border                -> P1
    - P2: Worth deeper diligence           -> P2
    - P3: Watch list                       -> P3
    - P4: Low priority / likely reject     -> P4

    New model:
    - P0: Highest-priority target          -> P0
    - P1: Near-priority target             -> P1
    - P2: Worth deeper diligence           -> P2
    - P3: Watch list                       -> P3
    - P4: Low priority / likely reject     -> P4
    """
    text = safe_text(value)

    if text == "":
        return ""

    lower = text.lower()

    # New P0 or old top-priority P1.
    # Keep this before the P1-border logic so old "P1: High-priority" maps up to P0.
    if (
        lower.startswith("p0")
        or "highest-priority" in lower
        or "highest priority" in lower
        or "active pursuit" in lower
        or "top-priority" in lower
        or "top priority" in lower
        or lower.startswith("p1: high-priority")
        or lower.startswith("p1: high priority")
        or lower.startswith("p1 - high-priority")
        or lower.startswith("p1 - high priority")
    ):
        return "P0: Highest-priority target"

    # New P1 / old P1-border.
    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or lower.startswith("p1 - near-priority")
        or lower.startswith("p1 - near priority")
        or "p1-border" in lower
        or "p1 border" in lower
        or "near-priority" in lower
        or "near priority" in lower
        or "strong p2" in lower
        or "p0-border" in lower
        or "p0 border" in lower
    ):
        return "P1: Near-priority target"

    # Clean P2
    if (
        lower.startswith("p2")
        or lower.startswith("review p2")
        or "review p2" in lower
        or "worth deeper diligence" in lower
        or "diligence target" in lower
        or "deeper diligence" in lower
    ):
        return "P2: Worth deeper diligence"

    # Clean P3.
    if (
        lower.startswith("p3")
        or "watch list" in lower
        or "watchlist" in lower
    ):
        return "P3: Watch list"

    # Clean P4.
    if (
        lower.startswith("p4")
        or "low priority" in lower
        or "likely reject" in lower
        or "weak fit" in lower
        or "reject" in lower
    ):
        return "P4: Low priority / likely reject"

    # Ambiguous bare P1:
    # In the new system, P1 means near-priority.
    # Historical old P1 should ideally include "High-priority target" and maps to P0 above.
    if lower == "p1":
        return "P1: Near-priority target"

    # Ambiguous / unmapped. Preserve text rather than destroying source context.
    return text

def priority_code(value):
    normalized = normalize_priority_level(value)
    return extract_priority_code(normalized)

def priority_rank(value):
    """
    Lower rank sorts earlier.
    P0 is the highest-priority bucket.
    """
    code = priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

# -----------------------------
# Apply priority fields
# -----------------------------

def apply_priority_fields(input_df):
    output_df = input_df.copy()

    if "priority_level" not in output_df.columns:
        output_df["priority_level"] = ""

    if "reviewed_priority_level" not in output_df.columns:
        output_df["reviewed_priority_level"] = ""

    if "priority_review_note" not in output_df.columns:
        output_df["priority_review_note"] = ""

    output_df["final_priority_level"] = output_df.apply(
        lambda row: normalize_priority_level(row.get("reviewed_priority_level", ""))
        if not is_blank_value(row.get("reviewed_priority_level", ""))
        else normalize_priority_level(row.get("priority_level", "")),
        axis=1
    )

    def determine_priority_source(row):
        auto_priority = normalize_priority_level(row.get("priority_level", ""))
        reviewed_priority = normalize_priority_level(row.get("reviewed_priority_level", ""))
        review_note = safe_text(row.get("priority_review_note", ""))

        if reviewed_priority == "":
            return "Auto Adjudicated"

        if reviewed_priority != auto_priority:
            return "Human Reviewed"

        if review_note != "":
            return "Human Reviewed"

        return "Auto Adjudicated"

    output_df["priority_source"] = output_df.apply(determine_priority_source, axis=1)

    output_df["final_priority_code"] = output_df["final_priority_level"].apply(priority_code)
    output_df["final_priority_rank"] = output_df["final_priority_level"].apply(priority_rank)

    output_df["decision_priority"] = output_df["final_priority_level"]
    output_df["decision_priority_sort"] = output_df["final_priority_rank"]

    return output_df

print("PASS: Step 12B priority helper loaded.")
print("Priority model:")
print("- P0 = Highest-priority target / old P1")
print("- P1 = Near-priority target / old P1-border")
print("- P2 = Worth deeper diligence")
print("- P3 = Watch list")
print("- P4 = Low priority / likely reject")



# =============================================================================

# Purpose:

# - Normalize priority labels into P0-P4 dashboard priority

# - Create final_priority_level, priority_source, final_priority_code, final_priority_rank

# - Preserve priority_level and reviewed_priority_level for traceability

# TODO: Paste current Step 12B Colab code here.

# =============================================================================

# STEP 13 - Load master dashboard using final priority

# =============================================================================

# 13 - Load master dashboard using final priority
# Purpose:
# - Load active master
# - Apply priority helper from Step 12B
# - Create final_priority_level using reviewed_priority_level first, then priority_level
# - Create priority_source for Auto Adjudicated vs Human Reviewed
# - Preserve decision_priority / decision_priority_sort as backward-compatible aliases for older dashboard steps
# - Does not modify or save the master

import pandas as pd
import shutil
from pathlib import Path
from google.colab import drive

drive.mount("/content/drive")

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_master_path = drive_folder / "health_tech_market_research_summary_MASTER.csv"
local_master_path = Path("health_tech_market_research_summary_MASTER.csv")

if not drive_master_path.exists():
    raise FileNotFoundError(f"Master not found: {drive_master_path}")

# Step 13 now depends on Step 12B.
# This prevents multiple cells from maintaining conflicting priority logic.
if "apply_priority_fields" not in globals():
    raise NameError(
        "STOP: apply_priority_fields is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

if "priority_rank" not in globals():
    raise NameError(
        "STOP: priority_rank is not defined. "
        "Run Step 12B - Priority field helper before Step 13."
    )

shutil.copy(drive_master_path, local_master_path)

master_df = pd.read_csv(local_master_path)

# -----------------------------
# Required baseline columns
# -----------------------------

if "company" not in master_df.columns:
    raise ValueError("STOP: Master is missing required column: company")

if "priority_level" not in master_df.columns:
    master_df["priority_level"] = ""

if "reviewed_priority_level" not in master_df.columns:
    master_df["reviewed_priority_level"] = ""

if "priority_review_note" not in master_df.columns:
    master_df["priority_review_note"] = ""

# -----------------------------
# Apply final priority logic from Step 12B
# -----------------------------

master_df = apply_priority_fields(master_df)

# Backward-compatible aliases for steps that still reference old names.
# These should eventually be replaced downstream with final_priority_level / final_priority_rank.
master_df["decision_priority"] = master_df["final_priority_level"]
master_df["decision_priority_sort"] = master_df["final_priority_rank"]

# -----------------------------
# Sort dashboard-ready master
# -----------------------------

sort_cols = []
ascending = []

if "final_priority_rank" in master_df.columns:
    sort_cols.append("final_priority_rank")
    ascending.append(True)

for col in [
    "pmf_scale_score",
    "thesis_fit_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "evidence_confidence_score"
]:
    if col in master_df.columns:
        sort_cols.append(col)
        ascending.append(False)

if sort_cols:
    master_df = master_df.sort_values(
        by=sort_cols,
        ascending=ascending
    ).reset_index(drop=True)

# -----------------------------
# Output summary
# -----------------------------

print("Master loaded for dashboard use.")
print("Master shape:", master_df.shape)
print("Company count:", master_df["company"].nunique())

print("\nFinal priority summary:")
priority_summary = (
    master_df
    .groupby(["final_priority_level", "priority_source"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
)

priority_summary["priority_sort"] = priority_summary["final_priority_level"].apply(priority_rank)

priority_summary = priority_summary.sort_values(
    by=["priority_sort", "priority_source"],
    ascending=[True, True]
).drop(columns=["priority_sort"])

display(priority_summary)

print("\nPriority source summary:")
display(
    master_df
    .groupby("priority_source", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values("priority_source")
)

human_reviewed_df = master_df[
    master_df["priority_source"].astype(str).str.lower().eq("human reviewed")
].copy()

if not human_reviewed_df.empty:
    print("\nHuman-reviewed priority overrides:")
    override_cols = [
        "company",
        "priority_level",
        "reviewed_priority_level",
        "final_priority_level",
        "priority_review_note"
    ]
    override_cols = [col for col in override_cols if col in human_reviewed_df.columns]

    display(
        human_reviewed_df[override_cols]
        .sort_values("final_priority_level")
        .reset_index(drop=True)
    )
else:
    print("\nNo human-reviewed priority overrides found.")

print("\nDashboard priority fields available:")
print("- priority_level = auto/adjudicated system priority")
print("- reviewed_priority_level = optional human override")
print("- final_priority_level = dashboard priority")
print("- priority_source = Auto Adjudicated or Human Reviewed")
print("- final_priority_rank = hidden/helper sort field")

# =============================================================================

# STEP 14 - Build market map view

# =============================================================================

# 14 - Build market map view
# Purpose:
# - Build a dashboard-ready market_map_df from master_df
# - Use final_priority_level / final_priority_rank from Step 12B as the priority source of truth
# - Restore market segment mapping
# - Create P0-aware strategic_bucket values
# - Preserve backward-compatible aliases for older downstream cells
#
# Run after:
# 12B -> 13
#
# Then continue:
# 15 -> 16 -> 17 -> 18 -> 19 -> 19A

import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime

# -----------------------------
# Validate inputs
# -----------------------------

if "master_df" not in globals() or not isinstance(master_df, pd.DataFrame) or master_df.empty:
    raise NameError("STOP: master_df not found or empty. Run Step 13 first.")

market_map_df = master_df.copy()

# Step 14 depends on Step 12B priority helper.
if "apply_priority_fields" in globals():
    market_map_df = apply_priority_fields(market_map_df)
else:
    raise NameError(
        "STOP: apply_priority_fields is not defined. "
        "Run Step 12B before Step 14."
    )

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def normalize_name(value):
    text = safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_final_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def final_priority_rank_from_level(value):
    code = extract_final_priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

def existing_cols(df, cols):
    return [col for col in cols if col in df.columns]

# -----------------------------
# Required fields
# -----------------------------

default_columns = {
    "company": "",
    "market_segment": "",
    "strategic_bucket": "",
    "final_priority_level": "",
    "priority_source": "",
    "final_priority_code": "",
    "final_priority_rank": 99,
    "priority_level": "",
    "reviewed_priority_level": "",
    "priority_review_note": "",
    "thesis_fit_score": np.nan,
    "pmf_scale_score": np.nan,
    "evidence_confidence_score": np.nan,
    "katelynd_role_fit_score": np.nan,
    "operator_timing_score": np.nan,
    "business_model_classification": "",
    "commercial_scale_assessment": "",
    "pmf_scale_assessment": "",
    "final_recommendation": "",
    "final_takeaway": "",
    "calibration_flag": ""
}

for col_name, default_value in default_columns.items():
    if col_name not in market_map_df.columns:
        market_map_df[col_name] = default_value

for score_col in [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]:
    market_map_df[score_col] = pd.to_numeric(
        market_map_df[score_col],
        errors="coerce"
    )

# Force clean P0-P4 code/rank in case any older downstream logic is stale.
market_map_df["final_priority_code"] = market_map_df["final_priority_level"].apply(extract_final_priority_code)
market_map_df["final_priority_rank"] = market_map_df["final_priority_level"].apply(final_priority_rank_from_level)

# Backward-compatible aliases.
market_map_df["decision_priority"] = market_map_df["final_priority_level"]
market_map_df["decision_priority_sort"] = market_map_df["final_priority_rank"]
market_map_df["reviewed_priority_rank"] = market_map_df["final_priority_rank"]

# -----------------------------
# Market segment mapping
# -----------------------------
# Keep an existing nonblank/non-Unmapped market_segment if present.
# Otherwise, map known companies into research segments.

segment_map = {
    # Nutrition, metabolic health, obesity, food as medicine
    "nourish": "Nutrition / food as medicine",
    "fay nutrition": "Nutrition / food as medicine",
    "berry street": "Nutrition / food as medicine",
    "culina health": "Nutrition / food as medicine",
    "9amhealth": "Metabolic health / virtual care",
    "noom med": "Metabolic health / obesity care",
    "omada health": "Metabolic health / digital therapeutics",
    "levels health": "Metabolic health / D2C behavior change",
    "signos": "Metabolic health / D2C behavior change",
    "zoe": "Metabolic health / D2C behavior change",

    # GI / specialty care
    "oshi health": "GI / specialty virtual care",

    # Women’s health / family health
    "maven clinic": "Women’s and family health",
    "midi health": "Women’s and family health",
    "allara health": "Women’s and family health",
    "visana health": "Women’s and family health",
    "familywell health": "Women’s and family health",
    "oova": "Women’s health / fertility",

    # MSK
    "hinge health": "MSK / digital physical therapy",
    "sword health": "MSK / digital physical therapy",

    # Mental and behavioral health
    "equip health": "Behavioral health / eating disorder care",
    "grow therapy": "Mental health / provider marketplace",
    "headway mental health insurance network": "Mental health / insurance network",
    "headway": "Mental health / insurance network",
    "affect therapeutics": "Behavioral health / substance use treatment",

    # Navigation, advocacy, hybrid care
    "transcarent": "Care navigation / hybrid care",
    "solace health patient advocacy": "Care navigation / advocacy",
    "solace health": "Care navigation / advocacy",
    "angle health": "Health insurance / benefits infrastructure",
    "included health": "Care navigation / hybrid care",

    # Oncology / serious illness
    "jasper health": "Oncology / cancer navigation",
    "outcomes4me": "Oncology / cancer navigation",

    # Preventive health / diagnostics / wearables / clinical intelligence
    "function health": "Preventive health / diagnostics",
    "insidetracker": "Preventive health / diagnostics",
    "oura": "Wearables / consumer health",
    "openevidence": "Clinical AI / provider intelligence"
}

def map_market_segment(row):
    existing_segment = safe_text(row.get("market_segment", ""))

    if existing_segment and existing_segment.lower() not in ["unmapped", "unknown", "nan", "none"]:
        return existing_segment

    company_key = normalize_name(row.get("company", ""))

    if company_key in segment_map:
        return segment_map[company_key]

    # Fallback partial matching for names with descriptors.
    for known_name, segment in segment_map.items():
        if known_name in company_key or company_key in known_name:
            return segment

    return "Unmapped"

market_map_df["market_segment"] = market_map_df.apply(map_market_segment, axis=1)

# -----------------------------
# Strategic bucket mapping
# -----------------------------
# P0-aware replacement for old logic that treated P0 as unmapped/unprioritized.

def map_strategic_bucket(row):
    code = extract_final_priority_code(row.get("final_priority_level", ""))

    if code == "P0":
        return "Active pursuit / highest-priority target"

    if code == "P1":
        return "Priority target / near-priority"

    if code == "P2":
        return "Diligence target"

    if code == "P3":
        return "Watch list"

    if code == "P4":
        return "Low priority / likely reject"

    calibration_flag = safe_text(row.get("calibration_flag", ""))

    if calibration_flag:
        return "Needs review"

    return "Unprioritized"

market_map_df["strategic_bucket"] = market_map_df.apply(map_strategic_bucket, axis=1)

# -----------------------------
# Sort market map
# -----------------------------

sort_cols = []
ascending = []

for col_name, ascending_value in [
    ("final_priority_rank", True),
    ("thesis_fit_score", False),
    ("pmf_scale_score", False),
    ("katelynd_role_fit_score", False),
    ("operator_timing_score", False),
    ("evidence_confidence_score", False),
    ("company", True)
]:
    if col_name in market_map_df.columns:
        sort_cols.append(col_name)
        ascending.append(ascending_value)

if sort_cols:
    market_map_df = market_map_df.sort_values(
        by=sort_cols,
        ascending=ascending
    ).reset_index(drop=True)

# -----------------------------
# Save snapshot
# -----------------------------

snapshot_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
market_map_snapshot_path = Path(f"health_tech_market_map_snapshot_{snapshot_timestamp}.csv")
market_map_df.to_csv(market_map_snapshot_path, index=False)

# -----------------------------
# Output checks
# -----------------------------

print("Market map view built.")
print("Shape:", market_map_df.shape)
print("Snapshot:", market_map_snapshot_path)

print("\nFinal priority summary:")
priority_summary = (
    market_map_df
    .groupby(["final_priority_level", "priority_source"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
)

priority_summary["final_priority_rank"] = priority_summary["final_priority_level"].apply(final_priority_rank_from_level)

priority_summary = priority_summary.sort_values(
    by=["final_priority_rank", "priority_source"],
    ascending=[True, True]
).drop(columns=["final_priority_rank"])

display(priority_summary)

print("\nStrategic bucket summary:")
display(
    market_map_df
    .groupby("strategic_bucket", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values("company_count", ascending=False)
)

print("\nMarket segment summary:")
display(
    market_map_df
    .groupby("market_segment", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .sort_values(["company_count", "market_segment"], ascending=[False, True])
)

print("\nPreview:")
preview_cols = existing_cols(market_map_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_takeaway"
])

display(market_map_df[preview_cols].head(20))


# =============================================================================

# STEP 15 - Segment-level summary

# =============================================================================

# 15 - Segment-level summary
# Purpose:
# - Summarize market segments using final priority logic
# - Use final_priority_level / final_priority_rank as dashboard source of truth
# - Preserve visibility into priority_source and human-reviewed overrides

import pandas as pd
import numpy as np

if "market_map_df" not in globals():
    raise NameError("STOP: market_map_df is not defined. Run Step 14 first.")

required_cols = [
    "company",
    "market_segment",
    "final_priority_level",
    "final_priority_rank",
    "priority_source",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]

missing_cols = [col for col in required_cols if col not in market_map_df.columns]

if missing_cols:
    raise ValueError(f"STOP: market_map_df is missing required columns: {missing_cols}")

summary_df = market_map_df.copy()

# Optional columns for display
for col in ["review_status", "review_notes", "priority_review_note", "priority_level", "reviewed_priority_level"]:
    if col not in summary_df.columns:
        summary_df[col] = ""

# -----------------------------
# Segment summary
# -----------------------------

segment_summary = (
    summary_df
    .groupby("market_segment", dropna=False)
    .agg(
        company_count=("company", "nunique"),
        p1_count=("final_priority_level", lambda x: x.astype(str).str.contains("P1", case=False, na=False).sum()),
        p2_count=("final_priority_level", lambda x: x.astype(str).str.contains("P2", case=False, na=False).sum()),
        p3_count=("final_priority_level", lambda x: x.astype(str).str.contains("P3", case=False, na=False).sum()),
        p4_count=("final_priority_level", lambda x: x.astype(str).str.contains("P4", case=False, na=False).sum()),
        human_reviewed_count=("priority_source", lambda x: x.astype(str).str.contains("Human Reviewed", case=False, na=False).sum()),
        avg_thesis_fit=("thesis_fit_score", "mean"),
        avg_pmf_scale=("pmf_scale_score", "mean"),
        avg_evidence_confidence=("evidence_confidence_score", "mean"),
        avg_katelynd_role_fit=("katelynd_role_fit_score", "mean"),
        avg_operator_timing=("operator_timing_score", "mean"),
        best_final_priority_rank=("final_priority_rank", "min")
    )
    .reset_index()
)

# Round averages for readability
score_cols = [
    "avg_thesis_fit",
    "avg_pmf_scale",
    "avg_evidence_confidence",
    "avg_katelynd_role_fit",
    "avg_operator_timing"
]

for col in score_cols:
    segment_summary[col] = segment_summary[col].round(1)

segment_summary = segment_summary.sort_values(
    by=[
        "best_final_priority_rank",
        "p1_count",
        "p2_count",
        "avg_thesis_fit",
        "avg_operator_timing",
        "avg_pmf_scale"
    ],
    ascending=[True, False, False, False, False, False]
).reset_index(drop=True)

print("SEGMENT SUMMARY")
display(segment_summary)

# -----------------------------
# Companies by segment
# -----------------------------

company_by_segment_cols = [
    "market_segment",
    "company",
    "strategic_bucket",
    "final_priority_level",
    "priority_source",
    "priority_review_note",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "review_notes",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]

company_by_segment_cols = [col for col in company_by_segment_cols if col in summary_df.columns]

company_by_segment = (
    summary_df
    .sort_values(
        by=[
            "market_segment",
            "final_priority_rank",
            "thesis_fit_score",
            "operator_timing_score",
            "pmf_scale_score"
        ],
        ascending=[True, True, False, False, False]
    )
    [company_by_segment_cols]
    .reset_index(drop=True)
)

print("COMPANIES BY SEGMENT")
display(company_by_segment)

# -----------------------------
# Top / diligence targets
# -----------------------------

top_target_mask = (
    summary_df["final_priority_level"]
    .astype(str)
    .str.contains("P1|P2|Strong P2|P1-border|P1 border|Worth deeper diligence", case=False, na=False)
)

top_targets_cols = [
    "company",
    "market_segment",
    "strategic_bucket",
    "final_priority_level",
    "priority_source",
    "priority_review_note",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "review_notes",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]

top_targets_cols = [col for col in top_targets_cols if col in summary_df.columns]

top_targets = (
    summary_df[top_target_mask]
    .sort_values(
        by=[
            "final_priority_rank",
            "thesis_fit_score",
            "operator_timing_score",
            "pmf_scale_score"
        ],
        ascending=[True, False, False, False]
    )
    [top_targets_cols]
    .reset_index(drop=True)
)

print("TOP / DILIGENCE TARGETS")
display(top_targets)

# -----------------------------
# Human-reviewed overrides
# -----------------------------

human_reviewed = summary_df[
    summary_df["priority_source"].astype(str).str.contains("Human Reviewed", case=False, na=False)
].copy()

human_reviewed_cols = [
    "company",
    "market_segment",
    "priority_level",
    "reviewed_priority_level",
    "final_priority_level",
    "priority_review_note",
    "review_status",
    "review_notes"
]

human_reviewed_cols = [col for col in human_reviewed_cols if col in human_reviewed.columns]

print("HUMAN-REVIEWED PRIORITY OVERRIDES")
if human_reviewed.empty:
    print("No human-reviewed priority overrides found.")
else:
    display(
        human_reviewed[human_reviewed_cols]
        .sort_values(["final_priority_level", "company"])
        .reset_index(drop=True)
    )

# -----------------------------
# Unassigned companies
# -----------------------------

unassigned = summary_df[summary_df["market_segment"] == "Unassigned"].copy()

unassigned_cols = [
    "company",
    "final_priority_level",
    "priority_source",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "review_notes"
]

unassigned_cols = [col for col in unassigned_cols if col in unassigned.columns]

print("UNASSIGNED COMPANIES")
if unassigned.empty:
    print("No unassigned companies.")
else:
    display(
        unassigned[unassigned_cols]
        .sort_values(["final_priority_level", "company"])
        .reset_index(drop=True)
    )

# =============================================================================

# STEP 16 - Segment priority summary

# =============================================================================

# 16 - Segment priority summary
# Purpose:
# - Build segment-level priority summary using final_priority_level / final_priority_rank
# - Use strategic_bucket from Step 14
# - Use segment_summary from Step 15
# - Identify best companies per segment using final priority + scores

import pandas as pd
import numpy as np

if "market_map_df" not in globals():
    raise NameError("STOP: market_map_df is not defined. Run Step 14 first.")

if "segment_summary" not in globals():
    raise NameError("STOP: segment_summary is not defined. Run Step 15 first.")

required_market_cols = [
    "company",
    "market_segment",
    "strategic_bucket",
    "final_priority_level",
    "final_priority_rank",
    "thesis_fit_score",
    "pmf_scale_score",
    "operator_timing_score"
]

missing_market_cols = [col for col in required_market_cols if col not in market_map_df.columns]

if missing_market_cols:
    raise ValueError(f"STOP: market_map_df is missing required columns: {missing_market_cols}")

if "market_segment" not in segment_summary.columns:
    raise ValueError("STOP: segment_summary is missing required column: market_segment")

summary_source_df = market_map_df.copy()

# Optional fields
for col in [
    "priority_source",
    "priority_level",
    "reviewed_priority_level",
    "priority_review_note",
    "evidence_confidence_score",
    "katelynd_role_fit_score"
]:
    if col not in summary_source_df.columns:
        summary_source_df[col] = ""

# -----------------------------
# Strategic bucket counts by segment
# -----------------------------

priority_counts = (
    summary_source_df
    .pivot_table(
        index="market_segment",
        columns="strategic_bucket",
        values="company",
        aggfunc="nunique",
        fill_value=0
    )
    .reset_index()
)

# Flatten pivot column names just in case
priority_counts.columns = [
    str(col).strip() if not isinstance(col, tuple) else "_".join([str(x) for x in col if x])
    for col in priority_counts.columns
]

# -----------------------------
# Final priority counts by segment
# -----------------------------

final_priority_counts = (
    summary_source_df
    .pivot_table(
        index="market_segment",
        columns="final_priority_level",
        values="company",
        aggfunc="nunique",
        fill_value=0
    )
    .reset_index()
)

final_priority_counts.columns = [
    str(col).strip() if col == "market_segment" else f"count_{str(col).split(':')[0].strip()}"
    for col in final_priority_counts.columns
]

# -----------------------------
# Human-reviewed count by segment
# -----------------------------

human_reviewed_counts = (
    summary_source_df
    .assign(
        is_human_reviewed=lambda df: (
            df["priority_source"]
            .astype(str)
            .str.contains("Human Reviewed", case=False, na=False)
        )
    )
    .groupby("market_segment", dropna=False)
    .agg(
        human_reviewed_count=("is_human_reviewed", "sum")
    )
    .reset_index()
)

# -----------------------------
# Best companies per segment
# -----------------------------

best_companies = (
    summary_source_df
    .sort_values(
        by=[
            "market_segment",
            "final_priority_rank",
            "thesis_fit_score",
            "operator_timing_score",
            "pmf_scale_score"
        ],
        ascending=[True, True, False, False, False]
    )
    .groupby("market_segment", dropna=False)
    .agg(
        best_companies=(
            "company",
            lambda x: ", ".join(x.head(4))
        )
    )
    .reset_index()
)

# -----------------------------
# Best priority label per segment
# -----------------------------

best_priority_by_segment = (
    summary_source_df
    .sort_values(
        by=[
            "market_segment",
            "final_priority_rank",
            "thesis_fit_score",
            "operator_timing_score",
            "pmf_scale_score"
        ],
        ascending=[True, True, False, False, False]
    )
    .groupby("market_segment", dropna=False)
    .agg(
        best_final_priority_level=("final_priority_level", "first"),
        best_final_priority_rank=("final_priority_rank", "min")
    )
    .reset_index()
)

# -----------------------------
# Merge summaries
# -----------------------------

segment_priority_summary = (
    segment_summary
    .merge(
        priority_counts,
        on="market_segment",
        how="left"
    )
    .merge(
        final_priority_counts,
        on="market_segment",
        how="left"
    )
    .merge(
        human_reviewed_counts,
        on="market_segment",
        how="left"
    )
    .merge(
        best_companies,
        on="market_segment",
        how="left"
    )
    .merge(
        best_priority_by_segment,
        on="market_segment",
        how="left",
        suffixes=("", "_from_market_map")
    )
)

# Prefer best_final_priority_rank from Step 15 if already present; otherwise use merged version
if "best_final_priority_rank" not in segment_priority_summary.columns:
    if "best_final_priority_rank_from_market_map" in segment_priority_summary.columns:
        segment_priority_summary["best_final_priority_rank"] = segment_priority_summary["best_final_priority_rank_from_market_map"]

if "best_final_priority_rank_from_market_map" in segment_priority_summary.columns:
    segment_priority_summary = segment_priority_summary.drop(columns=["best_final_priority_rank_from_market_map"])

# Clean numeric count columns
count_cols = [
    col for col in segment_priority_summary.columns
    if col.startswith("count_")
    or col in [
        "Priority target",
        "Near-priority target",
        "Diligence target",
        "Evidence / role-fit review",
        "Watch list",
        "Low priority",
        "Unprioritized",
        "human_reviewed_count"
    ]
]

for col in count_cols:
    if col in segment_priority_summary.columns:
        segment_priority_summary[col] = (
            segment_priority_summary[col]
            .fillna(0)
            .astype(int)
        )

# -----------------------------
# Sort for dashboard usefulness
# -----------------------------

sort_cols = []
ascending = []

if "best_final_priority_rank" in segment_priority_summary.columns:
    sort_cols.append("best_final_priority_rank")
    ascending.append(True)

for col in [
    "p1_count",
    "p2_count",
    "avg_thesis_fit",
    "avg_operator_timing",
    "avg_pmf_scale"
]:
    if col in segment_priority_summary.columns:
        sort_cols.append(col)
        ascending.append(False)

if sort_cols:
    segment_priority_summary = segment_priority_summary.sort_values(
        by=sort_cols,
        ascending=ascending
    ).reset_index(drop=True)

print("SEGMENT PRIORITY SUMMARY")
display(segment_priority_summary)

# -----------------------------
# Optional quick view
# -----------------------------

quick_view_cols = [
    "market_segment",
    "company_count",
    "best_final_priority_level",
    "best_final_priority_rank",
    "p1_count",
    "p2_count",
    "p3_count",
    "p4_count",
    "Priority target",
    "Near-priority target",
    "Diligence target",
    "Watch list",
    "Low priority",
    "human_reviewed_count",
    "avg_thesis_fit",
    "avg_pmf_scale",
    "avg_katelynd_role_fit",
    "avg_operator_timing",
    "best_companies"
]

quick_view_cols = [col for col in quick_view_cols if col in segment_priority_summary.columns]

print("SEGMENT PRIORITY SUMMARY - QUICK VIEW")
display(segment_priority_summary[quick_view_cols])

# =============================================================================

# STEP 17 - Company data depth audit

# =============================================================================

# 17 - Company data depth audit
# Purpose:
# - Audit whether each company has recoverable raw research evidence
# - Use final_priority_level / final_priority_rank as dashboard source of truth
# - Preserve priority_level and reviewed_priority_level for traceability
# - Check raw evidence completeness across funding, payer/institutional, outcomes, commercial scale, and fit brief JSON

import pandas as pd
import json
import re
from pathlib import Path

if "master_df" not in globals():
    raise NameError("STOP: master_df is not defined. Run Step 13 first.")

master_summary_df = master_df.copy()

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def nonblank(value):
    return pd.notna(value) and str(value).strip() != ""

def clean_json_text(text):
    text = str(text).strip()
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()

def parseable_json(value):
    if not nonblank(value):
        return False

    try:
        raw = clean_json_text(value)
        start = raw.find("{")

        if start == -1:
            return False

        decoder = json.JSONDecoder()
        parsed, end = decoder.raw_decode(raw[start:])

        return isinstance(parsed, dict)

    except Exception:
        return False

def extract_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[1-4]\b", text)
    return match.group(0) if match else ""

def is_priority_target(value):
    code = extract_priority_code(value)
    return code in ["P1", "P2"]

# -----------------------------
# Build audit base
# -----------------------------

if "market_map_df" in globals():
    base_cols = [
        "company",
        "market_segment",
        "strategic_bucket",
        "final_priority_level",
        "priority_source",
        "priority_review_note",
        "priority_level",
        "reviewed_priority_level",
        "review_status",
        "review_notes",
        "thesis_fit_score",
        "pmf_scale_score",
        "evidence_confidence_score",
        "katelynd_role_fit_score",
        "operator_timing_score",
        "calibration_flag"
    ]

    base_cols = [col for col in base_cols if col in market_map_df.columns]

    audit_base = market_map_df[base_cols].copy()

else:
    audit_base = master_summary_df.copy()

    if "apply_priority_fields" in globals():
        audit_base = apply_priority_fields(audit_base)

    if "market_segment" not in audit_base.columns:
        audit_base["market_segment"] = ""

    if "strategic_bucket" not in audit_base.columns:
        audit_base["strategic_bucket"] = ""

# Ensure priority fields exist
for col in [
    "final_priority_level",
    "priority_source",
    "priority_review_note",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "review_notes",
    "calibration_flag"
]:
    if col not in audit_base.columns:
        audit_base[col] = ""

if "final_priority_rank" not in audit_base.columns:
    if "priority_rank" in globals():
        audit_base["final_priority_rank"] = audit_base["final_priority_level"].apply(priority_rank)
    else:
        audit_base["final_priority_rank"] = 99

# -----------------------------
# Find raw/checkpoint files that may contain full research evidence
# -----------------------------

candidate_paths = []

local_patterns = [
    "research_batches/*.csv",
    "health_tech_market_research_full_results.csv",
    "health_tech_market_research_results_checkpoint.csv",
    "health_tech_raw_research_ARCHIVE.csv"
]

for pattern in local_patterns:
    candidate_paths.extend(Path(".").glob(pattern))

# Include Drive archive/batch files if available
drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_batches_folder = drive_folder / "research_batches"

if drive_folder.exists():
    candidate_paths.append(drive_folder / "health_tech_raw_research_ARCHIVE.csv")
    candidate_paths.append(drive_folder / "health_tech_market_research_summary_MASTER.csv")

if drive_batches_folder.exists():
    candidate_paths.extend(drive_batches_folder.glob("*.csv"))

# Deduplicate paths
candidate_paths = sorted(set([path for path in candidate_paths if Path(path).exists()]))

raw_frames = []

for path in candidate_paths:
    try:
        temp = pd.read_csv(path)

        if "company" not in temp.columns:
            continue

        raw_cols = [
            "company",
            "date_researched",
            "funding_finding",
            "payer_institutional_finding",
            "outcomes_finding",
            "commercial_scale_finding",
            "fit_brief_json",
            "batch_name"
        ]

        available_cols = [col for col in raw_cols if col in temp.columns]

        evidence_cols = {
            "funding_finding",
            "payer_institutional_finding",
            "outcomes_finding",
            "commercial_scale_finding",
            "fit_brief_json"
        }

        # Only keep files with at least one raw evidence column
        if len(set(available_cols) & evidence_cols) == 0:
            continue

        temp = temp[available_cols].copy()
        temp["source_file"] = str(path)
        raw_frames.append(temp)

    except Exception as e:
        print(f"Skipping {path}: {e}")

if raw_frames:
    raw_inventory = pd.concat(raw_frames, ignore_index=True)
else:
    raw_inventory = pd.DataFrame(columns=[
        "company",
        "date_researched",
        "funding_finding",
        "payer_institutional_finding",
        "outcomes_finding",
        "commercial_scale_finding",
        "fit_brief_json",
        "batch_name",
        "source_file"
    ])

# -----------------------------
# Raw inventory completeness flags
# -----------------------------

for col in [
    "date_researched",
    "funding_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "commercial_scale_finding",
    "fit_brief_json",
    "batch_name",
    "source_file"
]:
    if col not in raw_inventory.columns:
        raw_inventory[col] = ""

raw_inventory["has_funding_raw"] = raw_inventory["funding_finding"].apply(nonblank)
raw_inventory["has_payer_raw"] = raw_inventory["payer_institutional_finding"].apply(nonblank)
raw_inventory["has_outcomes_raw"] = raw_inventory["outcomes_finding"].apply(nonblank)
raw_inventory["has_commercial_scale_raw"] = raw_inventory["commercial_scale_finding"].apply(nonblank)
raw_inventory["has_fit_brief_raw"] = raw_inventory["fit_brief_json"].apply(nonblank)
raw_inventory["fit_brief_json_parseable"] = raw_inventory["fit_brief_json"].apply(parseable_json)

raw_inventory["raw_completeness_score"] = (
    raw_inventory["has_funding_raw"].astype(int)
    + raw_inventory["has_payer_raw"].astype(int)
    + raw_inventory["has_outcomes_raw"].astype(int)
    + raw_inventory["has_commercial_scale_raw"].astype(int)
    + raw_inventory["has_fit_brief_raw"].astype(int)
    + raw_inventory["fit_brief_json_parseable"].astype(int)
)

# Optional date parsing for best-record selection
raw_inventory["date_researched_parsed"] = pd.to_datetime(
    raw_inventory["date_researched"],
    errors="coerce"
)

# -----------------------------
# Choose best raw record per company
# -----------------------------

if not raw_inventory.empty:
    raw_best = (
        raw_inventory
        .sort_values(
            by=[
                "company",
                "raw_completeness_score",
                "date_researched_parsed"
            ],
            ascending=[True, False, False]
        )
        .drop_duplicates(subset=["company"], keep="first")
    )

    raw_source_summary = (
        raw_inventory
        .groupby("company", dropna=False)
        .agg(
            raw_record_count=("company", "count"),
            raw_source_files=("source_file", lambda x: " | ".join(sorted(set([str(v) for v in x if nonblank(v)])))),
            raw_batch_names=("batch_name", lambda x: " | ".join(sorted(set([str(v) for v in x if nonblank(v)]))))
        )
        .reset_index()
    )

    raw_best = raw_best.merge(raw_source_summary, on="company", how="left")

else:
    raw_best = pd.DataFrame(columns=[
        "company",
        "raw_record_count",
        "raw_source_files",
        "raw_batch_names",
        "has_funding_raw",
        "has_payer_raw",
        "has_outcomes_raw",
        "has_commercial_scale_raw",
        "has_fit_brief_raw",
        "fit_brief_json_parseable",
        "raw_completeness_score"
    ])

# -----------------------------
# Merge audit base with raw evidence inventory
# -----------------------------

raw_best_cols = [
    "company",
    "raw_record_count",
    "raw_source_files",
    "raw_batch_names",
    "has_funding_raw",
    "has_payer_raw",
    "has_outcomes_raw",
    "has_commercial_scale_raw",
    "has_fit_brief_raw",
    "fit_brief_json_parseable",
    "raw_completeness_score"
]

raw_best_cols = [col for col in raw_best_cols if col in raw_best.columns]

data_depth_audit = audit_base.merge(
    raw_best[raw_best_cols],
    on="company",
    how="left"
)

# Fill missing raw indicators
for col in [
    "raw_record_count",
    "has_funding_raw",
    "has_payer_raw",
    "has_outcomes_raw",
    "has_commercial_scale_raw",
    "has_fit_brief_raw",
    "fit_brief_json_parseable",
    "raw_completeness_score"
]:
    if col not in data_depth_audit.columns:
        data_depth_audit[col] = 0

    data_depth_audit[col] = data_depth_audit[col].fillna(0)

data_depth_audit["raw_source_files"] = data_depth_audit.get("raw_source_files", "").fillna("")
data_depth_audit["raw_batch_names"] = data_depth_audit.get("raw_batch_names", "").fillna("")

# -----------------------------
# Data depth status logic
# -----------------------------

def depth_status(row):
    final_priority = safe_text(row.get("final_priority_level", ""))
    evidence = row.get("evidence_confidence_score", 0)
    calibration = safe_text(row.get("calibration_flag", ""))

    try:
        evidence = float(evidence)
    except Exception:
        evidence = 0

    if row["raw_record_count"] == 0:
        return "NEEDS RECOVERY: no raw record found"

    if row["raw_completeness_score"] < 5:
        return "NEEDS QA: incomplete raw evidence"

    if not bool(row["fit_brief_json_parseable"]):
        return "NEEDS QA: fit brief JSON not parseable"

    if "CHECK" in calibration:
        return "REVIEW FLAG: calibration check"

    if "REVIEW" in calibration:
        return "REVIEW FLAG: evidence caveat"

    if evidence < 50:
        return "REVIEW FLAG: low evidence confidence"

    if is_priority_target(final_priority) and evidence < 65:
        return "REVIEW FLAG: priority target with moderate evidence"

    return "OK"

data_depth_audit["data_depth_status"] = data_depth_audit.apply(depth_status, axis=1)

status_rank = {
    "NEEDS RECOVERY: no raw record found": 1,
    "NEEDS QA: incomplete raw evidence": 2,
    "NEEDS QA: fit brief JSON not parseable": 3,
    "REVIEW FLAG: calibration check": 4,
    "REVIEW FLAG: evidence caveat": 5,
    "REVIEW FLAG: low evidence confidence": 6,
    "REVIEW FLAG: priority target with moderate evidence": 7,
    "OK": 99
}

data_depth_audit["data_depth_status_rank"] = (
    data_depth_audit["data_depth_status"]
    .map(status_rank)
    .fillna(50)
    .astype(int)
)

# -----------------------------
# Sort audit
# -----------------------------

sort_cols = [
    "data_depth_status_rank",
    "final_priority_rank",
    "evidence_confidence_score",
    "company"
]

sort_cols = [col for col in sort_cols if col in data_depth_audit.columns]

data_depth_audit = data_depth_audit.sort_values(
    by=sort_cols,
    ascending=[True, True, True, True][:len(sort_cols)]
).reset_index(drop=True)

# -----------------------------
# Display audit
# -----------------------------

display_cols = [
    "company",
    "market_segment",
    "final_priority_level",
    "priority_source",
    "priority_level",
    "reviewed_priority_level",
    "review_status",
    "evidence_confidence_score",
    "calibration_flag",
    "raw_record_count",
    "raw_completeness_score",
    "has_funding_raw",
    "has_payer_raw",
    "has_outcomes_raw",
    "has_commercial_scale_raw",
    "has_fit_brief_raw",
    "fit_brief_json_parseable",
    "data_depth_status",
    "raw_batch_names",
    "raw_source_files"
]

display_cols = [col for col in display_cols if col in data_depth_audit.columns]

print("DATA DEPTH AUDIT")
display(data_depth_audit[display_cols])

print("SUMMARY BY DATA DEPTH STATUS")
display(
    data_depth_audit
    .groupby("data_depth_status", dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .assign(
        data_depth_status_rank=lambda df: df["data_depth_status"].map(status_rank).fillna(50).astype(int)
    )
    .sort_values("data_depth_status_rank")
    .drop(columns=["data_depth_status_rank"])
)

print("SUMMARY BY FINAL PRIORITY AND DATA DEPTH STATUS")
display(
    data_depth_audit
    .groupby(["final_priority_level", "data_depth_status"], dropna=False)
    .agg(company_count=("company", "nunique"))
    .reset_index()
    .assign(
        final_priority_rank=lambda df: df["final_priority_level"].apply(priority_rank) if "priority_rank" in globals() else 99,
        data_depth_status_rank=lambda df: df["data_depth_status"].map(status_rank).fillna(50).astype(int)
    )
    .sort_values(["final_priority_rank", "data_depth_status_rank"])
    .drop(columns=["final_priority_rank", "data_depth_status_rank"])
)

# =============================================================================

# STEP 18 - Segment coverage audit

# =============================================================================

# 18 - Segment coverage audit
# Purpose:
# - Audit whether each market segment has enough companies for a useful directional read
# - Use final_priority_level / final_priority_rank from Step 12B as the priority source of truth
# - Treat P0, P1, and P2 as priority-or-diligence companies
# - Treat P3 and P4 as watch/low-priority companies
# - Add P0-aware priority counts for dashboard export
#
# Run after:
# 12B -> 13 -> 14 -> 15 -> 16 -> 17
#
# Then continue:
# 19 -> 19A

import pandas as pd
import numpy as np
import re

# -----------------------------
# Validate inputs
# -----------------------------

if "market_map_df" not in globals() or not isinstance(market_map_df, pd.DataFrame) or market_map_df.empty:
    raise NameError("STOP: market_map_df not found or empty. Run Step 14 first.")

coverage_source_df = market_map_df.copy()

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()

def extract_final_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def final_priority_rank_from_code(code):
    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

def final_priority_rank_from_level(value):
    return final_priority_rank_from_code(extract_final_priority_code(value))

def existing_cols(df, cols):
    return [col for col in cols if col in df.columns]

def join_unique(values, max_items=8):
    clean_values = []

    for value in values:
        text = safe_text(value)
        if text and text not in clean_values:
            clean_values.append(text)

    if len(clean_values) > max_items:
        return ", ".join(clean_values[:max_items]) + f", +{len(clean_values) - max_items} more"

    return ", ".join(clean_values)

def coverage_status_from_counts(company_count, priority_or_diligence_count):
    """
    Directional coverage logic:
    - Strong read: at least 3 companies in the segment and at least 2 P0/P1/P2 companies
    - Directional read: at least 2 companies and at least 1 P0/P1/P2 company
    - Sparse / needs more companies: anything below that threshold
    """
    if company_count >= 3 and priority_or_diligence_count >= 2:
        return "Strong segment read"

    if company_count >= 2 and priority_or_diligence_count >= 1:
        return "Directional segment read"

    return "Sparse / needs more companies"

def coverage_status_rank(status):
    status_text = safe_text(status).lower()

    if status_text == "strong segment read":
        return 1

    if status_text == "directional segment read":
        return 2

    if status_text == "sparse / needs more companies":
        return 3

    return 99

def companies_needed_for_directional_read(company_count, priority_or_diligence_count):
    needed_company_count = max(0, 2 - int(company_count))
    needed_priority_count = max(0, 1 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)

def companies_needed_for_stronger_read(company_count, priority_or_diligence_count):
    needed_company_count = max(0, 3 - int(company_count))
    needed_priority_count = max(0, 2 - int(priority_or_diligence_count))
    return max(needed_company_count, needed_priority_count)

# -----------------------------
# Required columns
# -----------------------------

required_defaults = {
    "company": "",
    "market_segment": "Unmapped",
    "strategic_bucket": "",
    "final_priority_level": "",
    "priority_source": "",
    "final_priority_code": "",
    "final_priority_rank": 99,
    "thesis_fit_score": np.nan,
    "pmf_scale_score": np.nan,
    "evidence_confidence_score": np.nan,
    "katelynd_role_fit_score": np.nan,
    "operator_timing_score": np.nan
}

for col_name, default_value in required_defaults.items():
    if col_name not in coverage_source_df.columns:
        coverage_source_df[col_name] = default_value

for score_col in [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]:
    coverage_source_df[score_col] = pd.to_numeric(
        coverage_source_df[score_col],
        errors="coerce"
    )

coverage_source_df["final_priority_code"] = coverage_source_df["final_priority_level"].apply(extract_final_priority_code)
coverage_source_df["final_priority_rank"] = coverage_source_df["final_priority_level"].apply(final_priority_rank_from_level)

# -----------------------------
# Build segment coverage audit
# -----------------------------

segment_rows = []

for segment, segment_df in coverage_source_df.groupby("market_segment", dropna=False):
    working_df = segment_df.copy()

    company_count = working_df["company"].nunique()

    p0_count = int((working_df["final_priority_code"] == "P0").sum())
    p1_count = int((working_df["final_priority_code"] == "P1").sum())
    p2_count = int((working_df["final_priority_code"] == "P2").sum())
    p3_count = int((working_df["final_priority_code"] == "P3").sum())
    p4_count = int((working_df["final_priority_code"] == "P4").sum())

    priority_or_diligence_count = p0_count + p1_count + p2_count
    watch_or_low_count = p3_count + p4_count

    human_reviewed_count = int(
        working_df["priority_source"]
        .astype(str)
        .str.lower()
        .eq("human reviewed")
        .sum()
    )

    best_rank = int(working_df["final_priority_rank"].min()) if not working_df.empty else 99

    best_priority_levels = (
        working_df.loc[working_df["final_priority_rank"] == best_rank, "final_priority_level"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    best_final_priority_level = best_priority_levels[0] if best_priority_levels else ""

    top_companies_df = working_df.sort_values(
        by=[
            "final_priority_rank",
            "thesis_fit_score",
            "pmf_scale_score",
            "katelynd_role_fit_score",
            "operator_timing_score",
            "evidence_confidence_score",
            "company"
        ],
        ascending=[True, False, False, False, False, False, True]
    ).copy()

    best_companies = join_unique(top_companies_df["company"].head(5).tolist(), max_items=5)

    status = coverage_status_from_counts(company_count, priority_or_diligence_count)

    segment_rows.append({
        "market_segment": safe_text(segment) if safe_text(segment) else "Unmapped",
        "coverage_status": status,
        "coverage_status_rank": coverage_status_rank(status),
        "company_count": int(company_count),
        "priority_or_diligence_count": int(priority_or_diligence_count),
        "watch_or_low_count": int(watch_or_low_count),
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "p3_count": p3_count,
        "p4_count": p4_count,
        "human_reviewed_count": human_reviewed_count,
        "avg_thesis_fit": round(working_df["thesis_fit_score"].mean(), 1),
        "avg_pmf_scale": round(working_df["pmf_scale_score"].mean(), 1),
        "avg_evidence_confidence": round(working_df["evidence_confidence_score"].mean(), 1),
        "avg_katelynd_role_fit": round(working_df["katelynd_role_fit_score"].mean(), 1),
        "avg_operator_timing": round(working_df["operator_timing_score"].mean(), 1),
        "best_final_priority_level": best_final_priority_level,
        "best_final_priority_rank": best_rank,
        "current_best_companies": best_companies,
        "companies_needed_for_directional_read": companies_needed_for_directional_read(
            company_count,
            priority_or_diligence_count
        ),
        "companies_needed_for_stronger_read": companies_needed_for_stronger_read(
            company_count,
            priority_or_diligence_count
        )
    })

segment_coverage_audit = pd.DataFrame(segment_rows)

segment_coverage_audit = segment_coverage_audit.sort_values(
    by=[
        "coverage_status_rank",
        "best_final_priority_rank",
        "priority_or_diligence_count",
        "company_count",
        "avg_thesis_fit",
        "market_segment"
    ],
    ascending=[True, True, False, False, False, True]
).reset_index(drop=True)

# -----------------------------
# Output
# -----------------------------

print("Segment coverage audit built.")
print("Segment count:", segment_coverage_audit["market_segment"].nunique())
print("Shape:", segment_coverage_audit.shape)

print("\nCoverage status summary:")
display(
    segment_coverage_audit
    .groupby("coverage_status", dropna=False)
    .agg(segment_count=("market_segment", "nunique"))
    .reset_index()
    .sort_values("segment_count", ascending=False)
)

print("\nPriority / diligence coverage summary:")
display(
    segment_coverage_audit[[
        "market_segment",
        "coverage_status",
        "company_count",
        "priority_or_diligence_count",
        "p0_count",
        "p1_count",
        "p2_count",
        "p3_count",
        "p4_count",
        "best_final_priority_level",
        "current_best_companies"
    ]]
)

print("\nP0 segment check:")
display(
    segment_coverage_audit[
        segment_coverage_audit["p0_count"] > 0
    ][[
        "market_segment",
        "company_count",
        "priority_or_diligence_count",
        "p0_count",
        "p1_count",
        "p2_count",
        "best_final_priority_level",
        "current_best_companies"
    ]]
)


# =============================================================================

# STEP 19 - Export dashboard workbook

# =============================================================================

# Purpose:

# - Export focused dashboard workbook

# - Keep Master Dashboard clean

# - Move priority traceability to Priority Logic Audit

# 19 - Export dashboard workbook
# Purpose:
# - Create a clean Excel workbook from the final-priority dashboard
# - Use final_priority_level as the dashboard priority source of truth
# - Support the P0/P1/P2/P3/P4 priority model
# - Keep Master Dashboard decision-ready
# - Move priority traceability fields to Priority Logic Audit
# - Save to Google Drive
# - Define dashboard_workbook_path for Step 19A formatting
#
# After this, run Step 19A to format and download the workbook.

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from google.colab import drive
import shutil
import re

drive.mount("/content/drive")

# -----------------------------
# Choose dashboard dataframe
# -----------------------------

if "market_map_df" in globals() and isinstance(market_map_df, pd.DataFrame) and not market_map_df.empty:
    dashboard_df = market_map_df.copy()
elif "master_df" in globals() and isinstance(master_df, pd.DataFrame) and not master_df.empty:
    dashboard_df = master_df.copy()
elif "master_summary_df" in globals() and isinstance(master_summary_df, pd.DataFrame) and not master_summary_df.empty:
    dashboard_df = master_summary_df.copy()
else:
    raise NameError("STOP: No dashboard dataframe found. Run Steps 13–14 first.")

# -----------------------------
# Paths
# -----------------------------

drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
drive_folder.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

local_export_path = Path(f"health_tech_dashboard_export_{timestamp}.xlsx")
drive_export_path = drive_folder / f"health_tech_dashboard_export_{timestamp}.xlsx"

# Step 19A uses these variables.
dashboard_workbook_path = local_export_path
output_workbook_path = local_export_path

# -----------------------------
# Helpers
# -----------------------------

def safe_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip()

def existing_cols(df, cols):
    return [col for col in cols if col in df.columns]

def local_extract_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def local_priority_rank(value):
    code = local_extract_priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

def local_normalize_priority(value):
    text = safe_text(value)

    if text == "":
        return ""

    lower = text.lower()

    if (
        lower.startswith("p0")
        or "highest-priority" in lower
        or "highest priority" in lower
        or "active pursuit" in lower
        or "top-priority" in lower
        or "top priority" in lower
        or lower.startswith("p1: high-priority")
        or lower.startswith("p1: high priority")
    ):
        return "P0: Highest-priority target"

    if (
        lower.startswith("p1: near-priority")
        or lower.startswith("p1: near priority")
        or "p1-border" in lower
        or "p1 border" in lower
        or "near-priority" in lower
        or "near priority" in lower
        or "strong p2" in lower
        or "p0-border" in lower
        or "p0 border" in lower
    ):
        return "P1: Near-priority target"

    if (
        lower.startswith("p2")
        or lower.startswith("review p2")
        or "review p2" in lower
        or "worth deeper diligence" in lower
        or "diligence target" in lower
        or "deeper diligence" in lower
    ):
        return "P2: Worth deeper diligence"

    if (
        lower.startswith("p3")
        or "watch list" in lower
        or "watchlist" in lower
    ):
        return "P3: Watch list"

    if (
        lower.startswith("p4")
        or "low priority" in lower
        or "likely reject" in lower
        or "weak fit" in lower
        or "reject" in lower
    ):
        return "P4: Low priority / likely reject"

    if lower == "p1":
        return "P1: Near-priority target"

    return text

def safe_sort(df, sort_cols, ascending=None):
    usable_cols = existing_cols(df, sort_cols)

    if not usable_cols:
        return df.copy()

    if ascending is None:
        usable_ascending = [True] * len(usable_cols)
    else:
        usable_ascending = ascending[:len(usable_cols)]

    return df.sort_values(
        by=usable_cols,
        ascending=usable_ascending
    ).copy()

def contains_priority(value, codes):
    code = local_extract_priority_code(value)
    return code in codes

def join_unique(values, max_items=6):
    cleaned = []

    for value in values:
        text = safe_text(value)
        if text and text not in cleaned:
            cleaned.append(text)

    if len(cleaned) > max_items:
        return ", ".join(cleaned[:max_items]) + f" + {len(cleaned) - max_items} more"

    return ", ".join(cleaned)

# -----------------------------
# Ensure final priority fields exist
# -----------------------------

if "apply_priority_fields" in globals():
    dashboard_df = apply_priority_fields(dashboard_df)
else:
    # Fallback only. Normal workflow should run Step 12B before Step 19.
    if "priority_level" not in dashboard_df.columns:
        dashboard_df["priority_level"] = ""

    if "reviewed_priority_level" not in dashboard_df.columns:
        dashboard_df["reviewed_priority_level"] = ""

    if "priority_review_note" not in dashboard_df.columns:
        dashboard_df["priority_review_note"] = ""

    dashboard_df["final_priority_level"] = dashboard_df.apply(
        lambda row: local_normalize_priority(row.get("reviewed_priority_level", ""))
        if safe_text(row.get("reviewed_priority_level", "")) != ""
        else local_normalize_priority(row.get("priority_level", "")),
        axis=1
    )

    def local_priority_source(row):
        auto_priority = local_normalize_priority(row.get("priority_level", ""))
        reviewed_priority = local_normalize_priority(row.get("reviewed_priority_level", ""))
        review_note = safe_text(row.get("priority_review_note", ""))

        if reviewed_priority == "":
            return "Auto Adjudicated"

        if reviewed_priority != auto_priority:
            return "Human Reviewed"

        if review_note != "":
            return "Human Reviewed"

        return "Auto Adjudicated"

    dashboard_df["priority_source"] = dashboard_df.apply(local_priority_source, axis=1)
    dashboard_df["final_priority_code"] = dashboard_df["final_priority_level"].apply(local_extract_priority_code)
    dashboard_df["final_priority_rank"] = dashboard_df["final_priority_level"].apply(local_priority_rank)

# Backward-compatible aliases. New dashboard logic should use final_priority_level / final_priority_rank.
dashboard_df["decision_priority"] = dashboard_df["final_priority_level"]
dashboard_df["decision_priority_sort"] = dashboard_df["final_priority_rank"]

# -----------------------------
# Ensure required support fields exist
# -----------------------------

default_columns = {
    "company": "",
    "market_segment": "Unmapped",
    "strategic_bucket": "Unmapped",
    "calibration_flag": "",
    "review_status": "",
    "review_notes": "",
    "priority_review_note": "",
    "priority_level": "",
    "reviewed_priority_level": "",
    "priority_source": "Auto Adjudicated",
    "final_priority_level": "",
    "final_priority_code": "",
    "final_priority_rank": 99,
    "final_recommendation": "",
    "business_model_classification": "",
    "commercial_scale_assessment": "",
    "pmf_scale_assessment": "",
    "commercial_scale_finding": "",
    "payer_institutional_finding": "",
    "outcomes_finding": "",
    "funding_finding": "",
    "final_takeaway": "",
    "thesis_fit_score": np.nan,
    "pmf_scale_score": np.nan,
    "evidence_confidence_score": np.nan,
    "katelynd_role_fit_score": np.nan,
    "operator_timing_score": np.nan
}

for col_name, default_value in default_columns.items():
    if col_name not in dashboard_df.columns:
        dashboard_df[col_name] = default_value

dashboard_df["final_priority_code"] = dashboard_df["final_priority_level"].apply(local_extract_priority_code)

dashboard_df["final_priority_rank"] = pd.to_numeric(
    dashboard_df["final_priority_rank"],
    errors="coerce"
).fillna(
    dashboard_df["final_priority_level"].apply(local_priority_rank)
).fillna(99).astype(int)

for score_col in [
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score"
]:
    dashboard_df[score_col] = pd.to_numeric(
        dashboard_df[score_col],
        errors="coerce"
    )

# -----------------------------
# Force clean P0-P4 final priority ranking
# -----------------------------

def extract_final_priority_code(value):
    text = safe_text(value).upper()
    match = re.search(r"\bP[0-4]\b", text)
    return match.group(0) if match else ""

def final_priority_rank_from_level(value):
    code = extract_final_priority_code(value)

    return {
        "P0": 0,
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }.get(code, 99)

dashboard_df["final_priority_code"] = dashboard_df["final_priority_level"].apply(extract_final_priority_code)
dashboard_df["final_priority_rank"] = dashboard_df["final_priority_level"].apply(final_priority_rank_from_level)

dashboard_df["decision_priority"] = dashboard_df["final_priority_level"]
dashboard_df["decision_priority_sort"] = dashboard_df["final_priority_rank"]

# -----------------------------
# Master Dashboard
# -----------------------------
# Clean decision view. Priority plumbing lives in Priority Logic Audit.

master_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "business_model_classification",
    "commercial_scale_assessment",
    "pmf_scale_assessment",
    "calibration_flag",
    "final_takeaway"
])

master_view = safe_sort(
    dashboard_df,
    [
        "final_priority_rank",
        "thesis_fit_score",
        "pmf_scale_score",
        "katelynd_role_fit_score",
        "operator_timing_score",
        "evidence_confidence_score"
    ],
    [True, False, False, False, False, False]
)[master_cols]

# -----------------------------
# Priority Focus
# -----------------------------
# P0/P1/P2 companies plus companies with calibration flags.

priority_focus_source = dashboard_df[
    dashboard_df["final_priority_level"].apply(lambda value: contains_priority(value, ["P0", "P1", "P2"]))
    | dashboard_df["calibration_flag"].astype(str).str.strip().ne("")
].copy()

priority_focus_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_recommendation",
    "business_model_classification",
    "commercial_scale_assessment",
    "calibration_flag",
    "final_takeaway"
])

priority_focus = safe_sort(
    priority_focus_source,
    [
        "final_priority_rank",
        "thesis_fit_score",
        "pmf_scale_score",
        "katelynd_role_fit_score",
        "operator_timing_score"
    ],
    [True, False, False, False, False]
)[priority_focus_cols]

# -----------------------------
# Segment Summary
# -----------------------------
# Build directly from dashboard_df so P0 is always included even if older Step 15 outputs exist.

segment_summary_export = (
    dashboard_df
    .groupby("market_segment", dropna=False)
    .agg(
        company_count=("company", "nunique"),
        p0_count=("final_priority_code", lambda x: (x.astype(str).str.upper() == "P0").sum()),
        p1_count=("final_priority_code", lambda x: (x.astype(str).str.upper() == "P1").sum()),
        p2_count=("final_priority_code", lambda x: (x.astype(str).str.upper() == "P2").sum()),
        p3_count=("final_priority_code", lambda x: (x.astype(str).str.upper() == "P3").sum()),
        p4_count=("final_priority_code", lambda x: (x.astype(str).str.upper() == "P4").sum()),
        human_reviewed_count=("priority_source", lambda x: x.astype(str).str.contains("Human Reviewed", case=False, na=False).sum()),
        avg_thesis_fit=("thesis_fit_score", "mean"),
        avg_pmf_scale=("pmf_scale_score", "mean"),
        avg_evidence_confidence=("evidence_confidence_score", "mean"),
        avg_katelynd_role_fit=("katelynd_role_fit_score", "mean"),
        avg_operator_timing=("operator_timing_score", "mean"),
        best_final_priority_rank=("final_priority_rank", "min")
    )
    .reset_index()
)

for avg_col in [
    "avg_thesis_fit",
    "avg_pmf_scale",
    "avg_evidence_confidence",
    "avg_katelynd_role_fit",
    "avg_operator_timing"
]:
    if avg_col in segment_summary_export.columns:
        segment_summary_export[avg_col] = segment_summary_export[avg_col].round(1)

best_priority_lookup = (
    dashboard_df
    .sort_values(["market_segment", "final_priority_rank", "thesis_fit_score"], ascending=[True, True, False])
    .groupby("market_segment", dropna=False)
    .agg(
        best_final_priority_level=("final_priority_level", "first"),
        best_companies=("company", lambda x: join_unique(x, max_items=5))
    )
    .reset_index()
)

segment_summary_export = segment_summary_export.merge(
    best_priority_lookup,
    on="market_segment",
    how="left"
)

segment_summary_export = safe_sort(
    segment_summary_export,
    ["best_final_priority_rank", "p0_count", "p1_count", "p2_count", "avg_thesis_fit"],
    [True, False, False, False, False]
)

# -----------------------------
# Companies by Segment
# -----------------------------

company_by_segment_cols = existing_cols(dashboard_df, [
    "market_segment",
    "company",
    "strategic_bucket",
    "final_priority_level",
    "priority_source",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "final_takeaway"
])

company_by_segment_export = safe_sort(
    dashboard_df[company_by_segment_cols],
    [
        "market_segment",
        "final_priority_rank",
        "thesis_fit_score",
        "operator_timing_score",
        "pmf_scale_score"
    ],
    [True, True, False, False, False]
)

# -----------------------------
# Commercial Scale Review
# -----------------------------

commercial_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "market_segment",
    "strategic_bucket",
    "pmf_scale_score",
    "evidence_confidence_score",
    "business_model_classification",
    "commercial_scale_assessment",
    "commercial_scale_finding",
    "payer_institutional_finding",
    "outcomes_finding",
    "calibration_flag",
    "final_takeaway"
])

commercial_review = safe_sort(
    dashboard_df[commercial_cols],
    ["final_priority_rank", "pmf_scale_score", "company"],
    [True, False, True]
)

# -----------------------------
# Data Depth Audit
# -----------------------------

if "data_depth_audit" in globals() and isinstance(data_depth_audit, pd.DataFrame) and not data_depth_audit.empty:
    data_depth_audit_export = data_depth_audit.copy()
else:
    audit_rows = []

    for _, row in dashboard_df.iterrows():
        audit_rows.append({
            "company": row.get("company", ""),
            "final_priority_level": row.get("final_priority_level", ""),
            "priority_source": row.get("priority_source", ""),
            "market_segment": row.get("market_segment", ""),
            "strategic_bucket": row.get("strategic_bucket", ""),
            "has_commercial_scale_assessment": safe_text(row.get("commercial_scale_assessment", "")) != "",
            "has_commercial_scale_finding": safe_text(row.get("commercial_scale_finding", "")) != "",
            "has_payer_institutional_finding": safe_text(row.get("payer_institutional_finding", "")) != "",
            "has_outcomes_finding": safe_text(row.get("outcomes_finding", "")) != "",
            "has_funding_finding": safe_text(row.get("funding_finding", "")) != "",
            "has_business_model_classification": safe_text(row.get("business_model_classification", "")) != "",
            "has_calibration_flag": safe_text(row.get("calibration_flag", "")) != ""
        })

    data_depth_audit_export = pd.DataFrame(audit_rows)

# -----------------------------
# Segment Coverage Audit
# -----------------------------

if "segment_coverage_audit" in globals() and isinstance(segment_coverage_audit, pd.DataFrame) and not segment_coverage_audit.empty:
    segment_coverage_audit_export = segment_coverage_audit.copy()
else:
    segment_coverage_audit_export = pd.DataFrame()

# -----------------------------
# Priority Logic Audit
# -----------------------------

priority_logic_cols = existing_cols(dashboard_df, [
    "company",
    "final_priority_level",
    "priority_source",
    "priority_review_note",
    "priority_level",
    "reviewed_priority_level",
    "final_priority_code",
    "final_priority_rank",
    "decision_priority",
    "decision_priority_sort",
    "review_status",
    "review_notes",
    "calibration_flag",
    "thesis_fit_score",
    "pmf_scale_score",
    "evidence_confidence_score",
    "katelynd_role_fit_score",
    "operator_timing_score",
    "market_segment",
    "strategic_bucket",
    "final_recommendation",
    "final_takeaway"
])

priority_logic_audit = safe_sort(
    dashboard_df[priority_logic_cols],
    ["final_priority_rank", "company"],
    [True, True]
)

# -----------------------------
# Read Me
# -----------------------------

read_me = pd.DataFrame([
    {
        "sheet": "Master Dashboard",
        "description": "Main decision dashboard. Uses Final Priority Level as the source of truth. Internal priority plumbing is intentionally excluded."
    },
    {
        "sheet": "Priority Focus",
        "description": "P0/P1/P2 companies plus any company with calibration flags."
    },
    {
        "sheet": "Segment Summary",
        "description": "P0-P4 segment-level scoring and priority roll-up."
    },
    {
        "sheet": "Companies by Segment",
        "description": "Company-level segment view sorted by final priority and fit scores."
    },
    {
        "sheet": "Commercial Scale Review",
        "description": "Commercial-scale and monetization evidence for revenue-quality review."
    },
    {
        "sheet": "Data Depth Audit",
        "description": "QA view showing whether key research evidence and fit-brief fields are populated."
    },
    {
        "sheet": "Segment Coverage Audit",
        "description": "Segment mapping sufficiency audit, included when Step 18 output is available."
    },
    {
        "sheet": "Priority Logic Audit",
        "description": "Traceability view showing automated priority, reviewed priority, final priority, source, and review notes."
    }
])

# -----------------------------
# Export workbook
# -----------------------------

with pd.ExcelWriter(local_export_path, engine="openpyxl") as writer:
    read_me.to_excel(writer, sheet_name="Read Me", index=False)
    master_view.to_excel(writer, sheet_name="Master Dashboard", index=False)
    priority_focus.to_excel(writer, sheet_name="Priority Focus", index=False)
    segment_summary_export.to_excel(writer, sheet_name="Segment Summary", index=False)
    company_by_segment_export.to_excel(writer, sheet_name="Companies by Segment", index=False)
    commercial_review.to_excel(writer, sheet_name="Commercial Scale Review", index=False)
    data_depth_audit_export.to_excel(writer, sheet_name="Data Depth Audit", index=False)

    if not segment_coverage_audit_export.empty:
        segment_coverage_audit_export.to_excel(writer, sheet_name="Segment Coverage Audit", index=False)

    priority_logic_audit.to_excel(writer, sheet_name="Priority Logic Audit", index=False)

shutil.copy(local_export_path, drive_export_path)

print("Dashboard export complete.")
print("Local file:", local_export_path)
print("Drive file:", drive_export_path)

print("\nWorkbook variable for Step 19A:")
print("dashboard_workbook_path =", dashboard_workbook_path)

print("\nExported sheets:")
exported_sheets = [
    "Read Me",
    "Master Dashboard",
    "Priority Focus",
    "Segment Summary",
    "Companies by Segment",
    "Commercial Scale Review",
    "Data Depth Audit"
]

if not segment_coverage_audit_export.empty:
    exported_sheets.append("Segment Coverage Audit")

exported_sheets.append("Priority Logic Audit")

for sheet in exported_sheets:
    print("-", sheet)

print("\nPriority Focus includes:")
print("- P0 companies")
print("- P1 companies")
print("- P2 companies")
print("- Any company with calibration flags")


# =============================================================================

# STEP 19A - Format exported dashboard workbook

# =============================================================================

# Purpose:

# - Convert headers to readable labels

# - Apply filters

# - Freeze header row

# - Set column widths

# - Wrap text

# - Save/copy/download formatted workbook

# 19A - Format exported dashboard workbook
# Purpose:
# - Convert snake_case headers to readable labels in the workbook only
# - Apply filters
# - Freeze header row
# - Set readable column widths
# - Wrap text for long cells
# - Save formatted workbook locally
# - Copy formatted workbook to Google Drive
# - Download formatted workbook

from pathlib import Path
import re
import shutil
from google.colab import files
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# -----------------------------
# Locate workbook
# -----------------------------

if "dashboard_workbook_path" in globals():
    workbook_path = Path(dashboard_workbook_path)
elif "market_map_workbook_path" in globals():
    workbook_path = Path(market_map_workbook_path)
elif "output_workbook_path" in globals():
    workbook_path = Path(output_workbook_path)
elif "local_export_path" in globals():
    workbook_path = Path(local_export_path)
else:
    raise NameError(
        "STOP: Could not find dashboard_workbook_path, market_map_workbook_path, "
        "output_workbook_path, or local_export_path."
    )

if not workbook_path.exists():
    raise FileNotFoundError(f"STOP: Workbook not found: {workbook_path}")

if "drive_export_path" in globals():
    formatted_drive_path = Path(drive_export_path)
else:
    drive_folder = Path("/content/drive/MyDrive/Job Search/Health Tech Research")
    drive_folder.mkdir(parents=True, exist_ok=True)
    formatted_drive_path = drive_folder / workbook_path.name

# -----------------------------
# Header formatting helpers
# -----------------------------

def friendly_header(header):
    if header is None:
        return ""

    text = str(header).strip()

    explicit_map = {
        "company": "Company",
        "priority_level": "Priority Level",
        "reviewed_priority_level": "Reviewed Priority Level",
        "final_priority_level": "Final Priority Level",
        "priority_source": "Priority Source",
        "priority_review_note": "Priority Review Note",
        "final_priority_code": "Final Priority Code",
        "final_priority_rank": "Final Priority Rank",
        "decision_priority": "Decision Priority",
        "decision_priority_sort": "Decision Priority Sort",
        "review_status": "Review Status",
        "review_notes": "Review Notes",
        "thesis_fit_score": "Thesis Fit Score",
        "pmf_scale_score": "PMF / Scale Score",
        "evidence_confidence_score": "Evidence Confidence Score",
        "katelynd_role_fit_score": "Katelynd Role Fit Score",
        "operator_timing_score": "Operator Timing Score",
        "final_recommendation": "Final Recommendation",
        "business_model_classification": "Business Model Classification",
        "commercial_scale_assessment": "Commercial Scale Assessment",
        "pmf_scale_assessment": "PMF / Scale Assessment",
        "scale_signal_assessment": "Scale Signal Assessment",
        "calibration_flag": "Calibration Flag",
        "final_takeaway": "Final Takeaway",
        "date_researched": "Date Researched",
        "funding_finding": "Funding Finding",
        "payer_institutional_finding": "Payer / Institutional Finding",
        "outcomes_finding": "Outcomes Finding",
        "commercial_scale_finding": "Commercial Scale Finding",
        "fit_brief_json": "Fit Brief JSON",
        "segment": "Segment",
        "market_segment": "Market Segment",
        "strategic_bucket": "Strategic Bucket",
        "company_stage": "Company Stage",
        "funding_stage": "Funding Stage",
        "revenue_estimate": "Revenue Estimate",
        "employee_count": "Employee Count",
        "source_urls": "Source URLs",
        "notes": "Notes",
        "company_count": "Company Count",
        "p1_count": "P1 Count",
        "p2_count": "P2 Count",
        "p3_count": "P3 Count",
        "p4_count": "P4 Count",
        "human_reviewed_count": "Human Reviewed Count",
        "avg_thesis_fit": "Avg. Thesis Fit",
        "avg_pmf_scale": "Avg. PMF / Scale",
        "avg_evidence_confidence": "Avg. Evidence Confidence",
        "avg_katelynd_role_fit": "Avg. Katelynd Role Fit",
        "avg_operator_timing": "Avg. Operator Timing",
        "best_final_priority_level": "Best Final Priority Level",
        "best_final_priority_rank": "Best Final Priority Rank",
        "best_companies": "Best Companies",
        "current_best_companies": "Current Best Companies",
        "coverage_status": "Coverage Status",
        "companies_needed_for_directional_read": "Companies Needed for Directional Read",
        "companies_needed_for_stronger_read": "Companies Needed for Stronger Read",
        "data_depth_status": "Data Depth Status",
        "raw_record_count": "Raw Record Count",
        "raw_completeness_score": "Raw Completeness Score",
        "has_funding_raw": "Has Funding Raw",
        "has_payer_raw": "Has Payer Raw",
        "has_outcomes_raw": "Has Outcomes Raw",
        "has_commercial_scale_raw": "Has Commercial Scale Raw",
        "has_fit_brief_raw": "Has Fit Brief Raw",
        "fit_brief_json_parseable": "Fit Brief JSON Parseable",
        "raw_source_files": "Raw Source Files",
        "raw_batch_names": "Raw Batch Names"
    }

    if text in explicit_map:
        return explicit_map[text]

    text = text.replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)

    small_words = {"and", "or", "to", "of", "in", "for", "with", "by"}

    words = []
    for i, word in enumerate(text.split(" ")):
        lower = word.lower()

        if i > 0 and lower in small_words:
            words.append(lower)
        elif lower == "pmf":
            words.append("PMF")
        elif lower == "d2c":
            words.append("D2C")
        elif lower == "b2b2c":
            words.append("B2B2C")
        elif lower == "arr":
            words.append("ARR")
        elif lower == "cac":
            words.append("CAC")
        elif lower == "api":
            words.append("API")
        elif lower == "json":
            words.append("JSON")
        elif lower == "qa":
            words.append("QA")
        else:
            words.append(word.capitalize())

    return " ".join(words)

def width_for_header(header):
    header_lower = str(header).lower()

    very_long_text_terms = [
        "assessment",
        "finding",
        "takeaway",
        "rationale",
        "notes",
        "claim",
        "source",
        "json",
        "description",
        "summary",
        "commercial",
        "outcomes",
        "institutional",
        "companies needed",
        "current best companies",
        "best companies",
        "raw source files",
        "raw batch names"
    ]

    medium_text_terms = [
        "classification",
        "recommendation",
        "priority",
        "business model",
        "segment",
        "flag",
        "status",
        "bucket",
        "source"
    ]

    if any(term in header_lower for term in very_long_text_terms):
        return 44

    if any(term in header_lower for term in medium_text_terms):
        return 26

    if "company" in header_lower:
        return 24

    if "score" in header_lower or "rank" in header_lower or "count" in header_lower:
        return 14

    if "date" in header_lower:
        return 16

    return 18

# -----------------------------
# Format workbook
# -----------------------------

wb = load_workbook(workbook_path)

header_fill = PatternFill("solid", fgColor="D9EAF7")
header_font = Font(bold=True, color="000000")
thin_border = Border(
    bottom=Side(style="thin", color="B7B7B7")
)

for ws in wb.worksheets:
    if ws.max_row < 1 or ws.max_column < 1:
        continue

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        original_header = cell.value
        display_header = friendly_header(original_header)

        cell.value = display_header
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

    ws.row_dimensions[1].height = 36

    for col_idx in range(1, ws.max_column + 1):
        col_letter = get_column_letter(col_idx)
        header_value = ws.cell(row=1, column=col_idx).value

        ws.column_dimensions[col_letter].width = width_for_header(header_value)

        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True
            )

    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 45

    for col_idx in range(1, ws.max_column + 1):
        header_value = str(ws.cell(row=1, column=col_idx).value or "").strip().lower()

        if header_value in [
            "final priority rank",
            "final priority code",
            "decision priority sort",
            "data depth status rank",
            "coverage status rank"
        ]:
            ws.column_dimensions[get_column_letter(col_idx)].hidden = True

# -----------------------------
# Save, sync, download
# -----------------------------

wb.save(workbook_path)
shutil.copy(workbook_path, formatted_drive_path)

print("PASS: Dashboard workbook formatted.")
print("Formatted local workbook:", workbook_path)
print("Formatted Drive workbook:", formatted_drive_path)

files.download(str(workbook_path))

