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

import json
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
    "funding_rounds_json",
]
COMMERCIAL_EVIDENCE_FIELDS = [
    "revenue_or_arr",
    "paying_customer_count",
    "user_scale_signal",
    "revenue_per_user",
    "growth_signal",
    "business_model_type",
    "funding_evidence",
    "q1_acquisition",
    "q2_monetization",
    "q3_funding_dependent",
    "q4_evidence_quality",
]

# Reset / restructure (Slice 3 + 3.5 multi-event) vocab.
# The seven recognized event types (no "none" — absence of events is the empty list).
RESET_EVENT_TYPES = frozenset(
    {"leadership-change", "declared-transformation", "founder-transition",
     "post-failure-rebuild", "restructuring-layoffs", "strategic-pivot", "ma-integration"}
)
# Recognized types that can NEVER fire reset (not high-agency openings).
RESET_NEVER_FIRE = frozenset({"strategic-pivot", "ma-integration"})
# Recognized types that CAN fire (with opening == yes). An unrecognized type is in NEITHER
# set: it does not fire and is surfaced via reset_needs_review (Slice 3.5 Flag 4).
RESET_FIREABLE_TYPES = frozenset(RESET_EVENT_TYPES - RESET_NEVER_FIRE)

# Columns produced by flatten_reset_fields (the derived signal/basis are persisted separately).
RESET_PERSIST_FIELDS = ["reset_events_json", "reset_event_types"]

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


# ---------------------------------------------------------------------------
# Funding-stage MAPPER (Rule 7, FRAMEWORK_VERSION v1.2) -- the LLM GATHERS dated rounds; CODE picks the
# stage. Replaces the old LLM-emitted funding_stage, which blinked across the round sequence (even the
# Allara control). SOT B4: a dated IPO/public event OUTRANKS any private round; else the latest-dated
# PRICED EQUITY round (bridge/extension/SAFE/debt + undated rounds excluded). Emits the SOT B4 vocab.
# ---------------------------------------------------------------------------

# Raw stage order for the same-date tiebreak (NOT collapsed -- series-d beats series-c on equal dates).
_STAGE_ORDER = [
    "pre-seed", "seed", "series-a", "series-b", "series-c",
    "series-d", "series-e", "series-f", "series-g", "series-h", "series-i",
]


def _is_true(value) -> bool:
    """Tolerate the LLM emitting a bool OR a string ('true'/'yes') for booleans like is_priced_equity."""
    return value is True or _norm(value) in {"true", "yes", "1"}


def _has_date(value) -> bool:
    """A round/event counts toward stage selection only with a real date -- 'unknown'/empty does not."""
    text = _norm(value)
    return bool(text) and text != "unknown"


def _parse_date(value) -> tuple[int, int]:
    """('YYYY' or 'YYYY-MM') -> (year, month). A bare year sorts at month 0 (so a more-specific same-year
    round sorts later). Never raises -- a malformed date that slips past _has_date -> (0, 0)."""
    try:
        parts = _norm(value).split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return (year, month)
    except (ValueError, IndexError, AttributeError):
        return (0, 0)


def _stage_rank(round_type) -> int:
    """Tiebreak rank for two rounds on the SAME date: the later stage wins (series-d > series-c)."""
    try:
        return _STAGE_ORDER.index(_norm_enum(round_type))
    except ValueError:
        return -1


def funding_stage_from_rounds(funding_rounds, ipo_event) -> str:
    """Deterministic funding_stage from the LLM-gathered dated rounds (Rule 7 -- the LLM never picks it).
    public-outranks (SOT B4 refinement 2); else the latest-dated PRICED EQUITY round (refinement 1:
    bridge/extension/SAFE/debt and undated rounds excluded). Returns the SOT B4 vocab, or 'unknown'."""
    rounds = funding_rounds if isinstance(funding_rounds, list) else []
    ipo = ipo_event if isinstance(ipo_event, dict) else {}
    if _is_true(ipo.get("occurred")) and _has_date(ipo.get("date")):
        return "public"
    priced = [
        r for r in rounds
        if isinstance(r, dict) and _is_true(r.get("is_priced_equity")) and _has_date(r.get("date"))
    ]
    if not priced:
        return "unknown"
    latest = max(priced, key=lambda r: (_parse_date(r.get("date")), _stage_rank(r.get("type"))))
    return _norm_stage(latest.get("type")) or "unknown"


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
    # B-rec (Rule 7): the LLM GATHERS dated rounds; funding_stage is DERIVED here by the deterministic
    # mapper -- the LLM never picks it. Raw rounds persist as a JSON evidence column (recomputable,
    # like reset_events_json).
    rounds = maturity.get("funding_rounds")
    out["funding_rounds_json"] = json.dumps(rounds) if isinstance(rounds, list) else ""
    out["funding_stage"] = funding_stage_from_rounds(rounds, maturity.get("ipo_event"))
    return out


# ---------------------------------------------------------------------------
# Reset / restructure (Slice 3.5 multi-event) — per-event opening evaluation.
# ---------------------------------------------------------------------------

def _reset_events_from(obj) -> list:
    """Normalize the carriers of the reset event list to a list of event dicts: the live
    reset_evidence dict ({"reset_events": [...]}), a stored row/dict with "reset_events_json"
    (string — recalibration), or a bare list."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        events = obj.get("reset_events")
        if isinstance(events, list):
            return events
        raw = obj.get("reset_events_json")
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                return []
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and isinstance(parsed.get("reset_events"), list):
                return parsed["reset_events"]
    return []


def derive_reset_signal(obj) -> bool:
    """Whether reset fires, evaluated PER EVENT (spec Slice 3.5).

    Fires IFF at least one event is a RECOGNIZED, fireable type (not strategic-pivot /
    ma-integration) AND that event's opening == "yes". A pivot's "no" can no longer bury a
    coexisting restructuring's "yes" — each event is judged on its own. Empty list -> False.
    An unrecognized event type does NOT fire (it is surfaced via reset_needs_review). Accepts
    the live reset_evidence dict OR a stored reset_events_json (recomputable without re-research);
    the engine's reset_signal(row) reads the materialized reset_or_restructure_signal this produces.
    """
    for ev in _reset_events_from(obj):
        if not isinstance(ev, dict):
            continue
        etype = _norm_reset_event(ev.get("event_type"))
        opening = _norm_enum(ev.get("creates_high_agency_opening"))
        if etype in RESET_FIREABLE_TYPES and opening == "yes":
            return True
    return False


def reset_needs_review(obj) -> bool:
    """True if any event carries a non-empty event_type that is NOT one of the seven recognized
    types (after normalization). Such events do not fire and are surfaced for human review
    rather than silently dropped or fired blind (Slice 3.5 Flag 4)."""
    for ev in _reset_events_from(obj):
        if not isinstance(ev, dict):
            continue
        etype = _norm_reset_event(ev.get("event_type"))
        if etype and etype not in RESET_EVENT_TYPES:
            return True
    return False


def reset_basis_for(obj) -> str:
    """Basis of the FIRING event (first that fires), else the first listed event's basis,
    else empty."""
    events = [ev for ev in _reset_events_from(obj) if isinstance(ev, dict)]
    for ev in events:
        etype = _norm_reset_event(ev.get("event_type"))
        opening = _norm_enum(ev.get("creates_high_agency_opening"))
        if etype in RESET_FIREABLE_TYPES and opening == "yes":
            return _safe_text(ev.get("basis"))
    return _safe_text(events[0].get("basis")) if events else ""


def flatten_reset_fields(parsed) -> dict:
    """Flatten reset_evidence into persisted columns: reset_events_json (the full event list —
    dashboard-visible and recomputable without re-research, per Part C) and reset_event_types
    (comma-joined types for scanning). Tolerant of missing block / non-dict / empty list."""
    reset_evidence = parsed.get("reset_evidence") if isinstance(parsed, dict) else None
    events = [ev for ev in _reset_events_from(reset_evidence) if isinstance(ev, dict)]
    types = ", ".join(t for t in (_safe_text(ev.get("event_type")) for ev in events) if t)
    return {
        "reset_events_json": json.dumps(events, ensure_ascii=False),
        "reset_event_types": types,
    }


# ---------------------------------------------------------------------------
# Capability-fit (Slice 4) — deterministic average of the three LLM-scored
# attributes, with the missing-attribute (null) policy. The LLM emits per-attribute
# scores (0-100) or null off the operating-characteristics evidence (Slice 3.7); this
# layer averages them and decides suppression. The engine repoint + the gate-time A1/A3
# recompute are SEPARATE commits — this is the averaging/flatten layer only.
# ---------------------------------------------------------------------------

CAPABILITY_FIELDS = [
    "capability_a1_score",
    "capability_a1_basis",
    "capability_a2_score",
    "capability_a2_basis",
    "capability_a3_score",
    "capability_a3_basis",
]

_SCORE_NULL_SENTINELS = {"", "null", "none", "n/a", "na", "nan", "unknown", "unscorable"}


def _score_or_none(value):
    """Parse a capability attribute score to a float, or None when unscorable.

    None / '' / 'null' / 'n/a' / non-numeric / NaN -> None ("couldn't assess").
    A real number -> float. CRITICAL: 0 is a real value (Absent band), NOT missing —
    only the null sentinels map to None.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # bool is an int subclass but is never a valid score
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = _norm(value)
    if text in _SCORE_NULL_SENTINELS:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def derive_capability_fit_score(a1, a2, a3) -> tuple[int | None, bool]:
    """Average the three capability attributes -> (katelynd_capability_fit_score, needs_review).

    Each input parses to a number or None ("couldn't assess"). If ANY is None ->
    ``(None, True)``: the overall score is SUPPRESSED and the row flagged for review — do NOT
    average the non-null remainder over a gap (Slice 4 policy). Otherwise ->
    ``(round(mean) clamped 0-100, False)``. CRITICAL: 0 is a real value and averages normally;
    ONLY None suppresses. The three components persist separately (flatten_capability_fields),
    so a flagged row stays re-judgable without re-research.
    """
    scores = [_score_or_none(a1), _score_or_none(a2), _score_or_none(a3)]
    if any(s is None for s in scores):
        return None, True
    avg = sum(scores) / 3.0
    return round(max(0.0, min(100.0, avg))), False


def flatten_capability_fields(parsed) -> dict:
    """Flatten capability_evidence into persisted columns (capability_a{1,2,3}_score/_basis).

    The three components persist REGARDLESS of the suppression outcome, so a row whose overall
    score is suppressed/flagged stays re-judgable without re-research. A null / unscorable score
    stores as None (re-reads as None via _score_or_none); a real 0 (Absent) is preserved as 0.0.
    Tolerant of a missing / non-dict block.
    """
    cap = parsed.get("capability_evidence") if isinstance(parsed, dict) else None
    cap = cap if isinstance(cap, dict) else {}
    return {
        "capability_a1_score": _score_or_none(cap.get("a1_score")),
        "capability_a1_basis": _safe_text(cap.get("a1_basis", "")),
        "capability_a2_score": _score_or_none(cap.get("a2_score")),
        "capability_a2_basis": _safe_text(cap.get("a2_basis", "")),
        "capability_a3_score": _score_or_none(cap.get("a3_score")),
        "capability_a3_basis": _safe_text(cap.get("a3_basis", "")),
    }
