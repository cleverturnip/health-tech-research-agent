"""Slice 2 — deterministic derivation of the maturity label and the 0-3 commercial
signal from STORED research components.

Spec: specs/slice2_structured_evidence_spec.md

Rule 7: the LLM gathers EVIDENCE (the maturity facts, the commercial facts, and the
four red-flag answers); these functions assign the maturity label and the commercial
signal. Both are PURE functions of the persisted columns, so the labels/signals are
recomputable without re-running research (Part C calibration principle): the expensive
part — gathering facts — runs once; the cheap part — derivation — re-runs freely.

Key separations the spec mandates:
- Maturity is anchored on funding stage ONLY. Revenue / ARR / valuation / scale never
  touch it (the Function Health fix: a Series B hypergrowth company is early-growth).
- The commercial signal structurally EXCLUDES funding; funding-dependence (q3) is a hard
  ceiling that can never be strong (the Solace fix).

v1 note: the MODERATE/WEAK boundary uses the PRESENCE of real revenue/paying-customer
evidence (not a parsed count). The "substantial vs. tiny" size boundary is deferred to
post-frame calibration (Part C) — STRONG is anchored on near-objective conditions
(genuine traction strength + evidence quality + not funding-dependent) and holds now.
"""

from __future__ import annotations

import math
import re

# ---------------------------------------------------------------------------
# Vocabulary (single source of truth)
# ---------------------------------------------------------------------------

FUNDING_STAGES = frozenset(
    {"pre-seed", "seed", "series-a", "series-b", "series-c", "series-d-plus", "public", "unknown"}
)
IPO_STATUSES = frozenset({"private", "filed", "public"})

# Maturity labels emitted by derive_maturity.
MATURITY_PUBLIC = "public"
MATURITY_NEAR_IPO = "near-ipo"
MATURITY_LATE_STAGE = "late-stage"
MATURITY_SCALE_UP = "scale-up"
MATURITY_EARLY_GROWTH = "early-growth"
MATURITY_EARLY = "early"
MATURITY_UNCLEAR = "unclear"

# Red-flag answer vocab.
GROWTH_VALUES = frozenset({"growing", "flat", "declining"})
Q2_VALUES = frozenset({"strong", "typical", "weak"})
Q4_VALUES = frozenset({"company-reported", "credible-estimate", "unverified-promotional"})
# Only these evidence qualities can support a STRONG signal (promotional is disqualifying).
Q4_STRONG_OK = frozenset({"company-reported", "credible-estimate"})

# 0-3 commercial signal <-> text (the engine reads the text via signal_text_to_score).
COMMERCIAL_SIGNAL_TEXT = {3: "strong", 2: "moderate", 1: "weak", 0: "none"}

# Fields flattened out of the fit-brief JSON (also the persisted master columns).
MATURITY_EVIDENCE_FIELDS = [
    "funding_stage",
    "ipo_status",
    "ipo_or_filing_date",
    "founding_year",
    "last_raise_date",
    "last_raise_amount",
    "total_funding",
    "funding_stage_evidence",
]
COMMERCIAL_EVIDENCE_FIELDS = [
    "revenue_or_arr",
    "paying_customer_count",
    "revenue_per_user",
    "growth_signal",
    "business_model_type",
    "funding_evidence",
    "q1_acquisition",
    "q2_monetization",
    "q3_funding_dependent",
    "q4_evidence_quality",
]

# Reset / restructure (Slice 3) vocab.
RESET_EVENT_TYPES = frozenset(
    {"none", "leadership-change", "declared-transformation", "founder-transition",
     "post-failure-rebuild", "restructuring-layoffs", "strategic-pivot", "ma-integration"}
)
# Event types that can NEVER fire reset (not high-agency openings). "none" is included so the
# logically-incoherent none + opening=yes case is structurally impossible — a real reset event
# is never typed "none", so this cannot suppress a legitimate reset (Slice 3 Flag 2).
RESET_NEVER_FIRE = frozenset({"strategic-pivot", "ma-integration", "none"})

RESET_EVIDENCE_FIELDS = [
    "reset_event_type",
    "reset_basis",
    "reset_creates_high_agency_opening",
]

# Sentinels that mean "no real evidence here" when a fact field is technically non-empty.
_ABSENT_SENTINELS = frozenset(
    {"", "none", "n/a", "na", "unknown", "no evidence", "not found", "not disclosed",
     "undisclosed", "no", "0", "null", "nan", "-", "—"}
)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _safe_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _norm(value) -> str:
    """Lowercase + trim; NaN/None -> ''."""
    return _safe_text(value).lower()


def _norm_enum(value) -> str:
    """Normalize a categorical value to hyphen-joined lowercase (e.g. 'Credible Estimate'
    -> 'credible-estimate', 'Series B' -> 'series-b')."""
    text = _norm(value)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def _norm_stage(value) -> str:
    """Normalize funding_stage to the vocab; collapse series-d and beyond to series-d-plus."""
    text = _norm_enum(value)
    if not text:
        return ""
    if text in {"pre-seed", "preseed"}:
        return "pre-seed"
    # series-d / series-d+ / series-d-plus / series-e / series-f / ... -> series-d-plus
    if re.match(r"^series-[d-z]", text):
        return "series-d-plus"
    return text


def _has_real_evidence(value) -> bool:
    """True when a fact field holds real evidence (non-empty and not an 'absent' sentinel)."""
    return _norm(value) not in _ABSENT_SENTINELS


def _norm_reset_event(value) -> str:
    """Normalize a reset_event_type to the vocab, folding common variants
    (e.g. 'M&A integration' / 'm&a-integration' -> 'ma-integration')."""
    text = _norm(value).replace("&", "")  # 'm&a' -> 'ma'
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


# ---------------------------------------------------------------------------
# Maturity (Part A) — funding stage anchors the label; revenue NEVER touches it.
# ---------------------------------------------------------------------------

def derive_maturity(row) -> tuple[str, bool]:
    """Return ``(maturity_label, needs_human_review)`` from the stored maturity facts.

    Funding stage / IPO status alone anchor maturity (spec Part A). Revenue, ARR,
    valuation, and growth are deliberately NOT read here. ``needs_human_review`` is
    True only when the stage is unknown / undeterminable (label ``"unclear"``).
    """
    ipo = _norm_enum(row.get("ipo_status"))
    stage = _norm_stage(row.get("funding_stage"))

    if ipo == "public":
        return MATURITY_PUBLIC, False
    if ipo == "filed":
        return MATURITY_NEAR_IPO, False

    if stage == "public":
        return MATURITY_PUBLIC, False
    if stage == "series-d-plus":
        return MATURITY_LATE_STAGE, False
    if stage == "series-c":
        return MATURITY_SCALE_UP, False
    if stage in {"series-a", "series-b"}:
        return MATURITY_EARLY_GROWTH, False
    if stage in {"seed", "pre-seed"}:
        return MATURITY_EARLY, False

    return MATURITY_UNCLEAR, True  # unknown / undeterminable -> flag for human review


# ---------------------------------------------------------------------------
# Commercial signal (Part B) — facts + four red-flags -> 0-3; funding excluded.
# ---------------------------------------------------------------------------

def derive_commercial_signal(row) -> int:
    """Return the 0-3 commercial signal from the stored facts + the four red-flags.

    Funding is structurally excluded. Funding-dependence (q3) is a HARD CEILING:
    it can never be strong. Credible estimates can support strong; only unverified /
    promotional evidence is disqualifying from strong. (Spec Part B.)

    v1: presence-based — "has real traction" means a non-empty revenue_or_arr OR
    paying_customer_count fact (not a parsed count); the moderate/weak size boundary
    is deferred to post-frame calibration (Part C).
    """
    q1 = _norm_enum(row.get("q1_acquisition"))       # growing / flat / declining
    q2 = _norm_enum(row.get("q2_monetization"))      # strong / typical / weak
    q3 = _norm_enum(row.get("q3_funding_dependent"))  # yes / no
    q4 = _norm_enum(row.get("q4_evidence_quality"))  # company-reported / credible-estimate / unverified-promotional

    has_real_traction = _has_real_evidence(row.get("revenue_or_arr")) or _has_real_evidence(
        row.get("paying_customer_count")
    )
    funding_dependent = q3 == "yes"
    q4_ok = q4 in Q4_STRONG_OK
    trap = q1 == "declining" and q2 == "weak"
    genuine_strength = (q2 == "strong") or (q1 == "growing" and has_real_traction)

    # STRONG (3): a genuine traction strength, credible evidence, not funding-dependent, not the trap.
    if genuine_strength and q4_ok and not funding_dependent and not trap:
        return 3
    # Would-be-strong resting only on unverified/promotional evidence -> capped at MODERATE.
    # (genuine_strength and trap are mutually exclusive, so this is the q4 cap.)
    if genuine_strength and not funding_dependent:
        return 2
    # Funding-dependence is a hard ceiling: never strong; moderate with real traction, weak without.
    if funding_dependent:
        return 2 if has_real_traction else 1
    # The trap: declining paying base AND weak monetization.
    if trap:
        return 1
    # Real paying customers / revenue exist, but no standout strength.
    if has_real_traction:
        return 2
    # No credible commercial evidence at all.
    return 0


def commercial_signal_to_text(score: int) -> str:
    """Map the 0-3 commercial signal to the text the engine reads (round-trips with
    candidate_priority.signal_text_to_score)."""
    return COMMERCIAL_SIGNAL_TEXT.get(int(score), "none")


# ---------------------------------------------------------------------------
# Flatten the Slice 2 evidence out of a parsed fit-brief into flat columns.
# ---------------------------------------------------------------------------

def flatten_slice2_fields(parsed) -> dict:
    """Extract the maturity + commercial evidence fields from a parsed fit-brief JSON
    into flat columns (empty string when a field/block is absent). Mirrors the existing
    scale-signal flatten; the derived label/signal are computed separately by the
    derive_* functions so they remain recomputable from these stored columns.
    """
    maturity = parsed.get("maturity_evidence") if isinstance(parsed, dict) else None
    commercial = parsed.get("commercial_evidence") if isinstance(parsed, dict) else None
    maturity = maturity if isinstance(maturity, dict) else {}
    commercial = commercial if isinstance(commercial, dict) else {}

    out = {}
    for field in MATURITY_EVIDENCE_FIELDS:
        out[field] = _safe_text(maturity.get(field, ""))
    for field in COMMERCIAL_EVIDENCE_FIELDS:
        out[field] = _safe_text(commercial.get(field, ""))
    return out


# ---------------------------------------------------------------------------
# Reset / restructure (Slice 3) — fires only for a genuine high-agency opening.
# ---------------------------------------------------------------------------

def derive_reset_signal(row) -> bool:
    """Return whether reset fires, from the stored researched fields (spec Slice 3).

    Reset fires IFF the event creates a high-agency opening AND the event type is not one
    that can never be an opening:

        reset = (reset_creates_high_agency_opening == "yes")
                and (reset_event_type NOT IN {strategic-pivot, ma-integration, none})

    strategic-pivot / ma-integration / none never fire. ``restructuring-layoffs`` is NOT
    pre-bucketed — it rides on the opening question (rebuild-toward-growth = yes -> fires;
    contraction-toward-decline = no -> does not). Pure function of stored fields; the engine's
    reset_signal(row) reads the materialized reset_or_restructure_signal this produces.
    """
    event = _norm_reset_event(row.get("reset_event_type"))
    opening = _norm_enum(row.get("reset_creates_high_agency_opening"))
    if event in RESET_NEVER_FIRE:
        return False
    return opening == "yes"


def flatten_reset_fields(parsed) -> dict:
    """Extract the reset_evidence fields from a parsed fit-brief JSON into flat columns
    (empty string when the block/field is absent; tolerant of non-dict input)."""
    reset = parsed.get("reset_evidence") if isinstance(parsed, dict) else None
    reset = reset if isinstance(reset, dict) else {}
    return {field: _safe_text(reset.get(field, "")) for field in RESET_EVIDENCE_FIELDS}
