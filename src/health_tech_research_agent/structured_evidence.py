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
    "sponsored_user_scale",
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
# The recognized event types (no "none" — absence of events is the empty list). `ipo-prep` was added
# v1.13 (§B4 faithful-fix): an emitted ipo-prep event is RECOGNIZED (not routed to reset_needs_review)
# and NEVER-fires (it is on RESET_NEVER_FIRE) — oura's confidential S-1 excludes cleanly, firing
# outcome unchanged. The emitter + this set must agree (SOT §B4 v1.13).
RESET_EVENT_TYPES = frozenset(
    {"leadership-change", "declared-transformation", "founder-transition",
     "post-failure-rebuild", "restructuring-layoffs", "strategic-pivot", "ma-integration", "ipo-prep"}
)
# Recognized types that can NEVER fire reset (not high-agency openings).
RESET_NEVER_FIRE = frozenset({"strategic-pivot", "ma-integration", "ipo-prep"})
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
    """Normalize a funding_stage / round-type to the SOT B4 vocab, or "" for a NON-CANONICAL type so the
    mapper EXCLUDES garbage ("Priced equity round" / "unknown" / "secondary sale" / "financing"). Folds
    'seed extension' -> seed and 'series-X extension' / 'series-X1' -> series-X; collapses series-d and
    beyond -> series-d-plus; keeps 'public'. Returning "" for a non-canonical type is what closes the
    mapper gap the source-directed re-measure exposed (audits/all_fields_probe_findings.md §14)."""
    text = _norm_enum(value)
    if not text:
        return ""
    if text == "public":
        return "public"
    if text.startswith("pre-seed") or text == "preseed":
        return "pre-seed"
    if text.startswith("seed"):                       # seed / seed-extension / seed-round -> seed
        return "seed"
    m = re.match(r"^series-([a-z])", text)            # series-a / series-a-extension / series-b1 -> base letter
    if m:
        return "series-d-plus" if m.group(1) >= "d" else f"series-{m.group(1)}"
    return ""                                         # non-canonical type -> EXCLUDED from stage selection


# The canonical PRIVATE-market stages a priced round may map to (public is the IPO branch, not a round).
_CANONICAL_STAGES = frozenset({"pre-seed", "seed", "series-a", "series-b", "series-c", "series-d-plus"})


# ---------------------------------------------------------------------------
# Funding-stage MAPPER (Rule 7, FRAMEWORK_VERSION v1.2) -- the LLM GATHERS dated rounds; CODE picks the
# stage. Replaces the old LLM-emitted funding_stage, which blinked across the round sequence (even the
# Allara control). SOT B4: a dated IPO/public event OUTRANKS any private round; else the latest-dated
# PRICED EQUITY round (bridge/extension/SAFE/debt + undated rounds excluded). Emits the SOT B4 vocab.
# ---------------------------------------------------------------------------

# Canonical stage order for the same-date tiebreak: the later stage wins (series-d-plus beats series-c).
_STAGE_ORDER = ["pre-seed", "seed", "series-a", "series-b", "series-c", "series-d-plus", "public"]


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


# §B4 v1.14 HUMAN-LOCKED STAGE OVERRIDE (the §B4 analogue of the §B2 B2B floor) — AUTHORITATIVE over the
# deterministic discriminator. signos/bicycle were TYPED series-c by the regen; the same-series-vs-new-
# series correction to series-b is human judgment NOT in the round record (SOT §B4 v1.14). 9amhealth needs
# NO entry (the discriminator gets series-b right). MAINTENANCE: doc-first edit to SOT §B4, not here.
DOCUMENTED_STAGE_OVERRIDES = {"signos": "series-b", "bicycle health": "series-b"}


def _round_series(r) -> str:
    """The round's DESIGNATED canonical series: an explicit ``series_designation`` when the synthesis
    provides one (v1.10 — honor an explicit designation), else the round ``type``. Normalized to the SOT
    B4 vocab ('' for a non-canonical / undesignated type, e.g. bridge / SAFE / 'Priced equity round')."""
    if not isinstance(r, dict):
        return ""
    return _norm_stage(r.get("series_designation")) or _norm_stage(r.get("type"))


def _stage_order_index(stage) -> int:
    """Index of a normalized stage in _STAGE_ORDER (later stage = higher); -1 if non-canonical."""
    try:
        return _STAGE_ORDER.index(stage)
    except ValueError:
        return -1


def _designated_rounds(rounds) -> list:
    """Priced, dated rounds carrying a canonical series DESIGNATION — the candidates for stage."""
    return [
        r for r in (rounds if isinstance(rounds, list) else [])
        if isinstance(r, dict) and _is_true(r.get("is_priced_equity")) and _has_date(r.get("date"))
        and _round_series(r) in _CANONICAL_STAGES
    ]


def funding_stage_from_rounds(funding_rounds, ipo_event) -> str:
    """Deterministic funding_stage from the LLM-gathered dated rounds (Rule 7 -- the LLM never picks it).
    SOT §B4 v1.10 DESIGNATED-SERIES discriminator: public outranks; else the LAST DESIGNATED canonical
    series by date -- a SAME-SERIES later round keeps the stage at that series (it carries the same
    designation, so it does not advance), and a non-canonical / undesignated / undated / bridge / SAFE /
    debt round does NOT advance it. Honors an explicit per-round ``series_designation`` when present (else
    the round ``type``). Returns the SOT B4 vocab, or 'unknown'. The §B4 v1.14 human-locked override is
    applied by ``resolve_funding_stage``, NOT here -- this stays the pure deterministic read."""
    ipo = ipo_event if isinstance(ipo_event, dict) else {}
    if _is_true(ipo.get("occurred")) and _has_date(ipo.get("date")):
        return "public"
    designated = _designated_rounds(funding_rounds)
    if not designated:
        return "unknown"
    latest = max(designated, key=lambda r: (_parse_date(r.get("date")), _stage_order_index(_round_series(r))))
    return _round_series(latest) or "unknown"


def funding_stage_with_confidence(funding_rounds, ipo_event) -> tuple[str, str]:
    """``(stage, stage_confidence)`` — SOT §B4 v1.10. stage_confidence == 'low' when a PRICED, DATED round
    is dated AFTER the last designated round but is NOT a canonical designation (an undesignated later
    round: we keep the last CONFIRMED designated series, but the most-recent capital is ambiguous -- flag,
    don't guess, Rule 8). Otherwise 'high'. public / unknown -> 'high' (handled elsewhere)."""
    stage = funding_stage_from_rounds(funding_rounds, ipo_event)
    if stage in ("public", "unknown"):
        return stage, "high"
    designated = _designated_rounds(funding_rounds)
    last_date = max(_parse_date(r.get("date")) for r in designated)
    rounds = funding_rounds if isinstance(funding_rounds, list) else []
    undesignated_later = any(
        isinstance(r, dict) and _is_true(r.get("is_priced_equity")) and _has_date(r.get("date"))
        and _round_series(r) not in _CANONICAL_STAGES
        and _parse_date(r.get("date")) > last_date
        for r in rounds
    )
    return stage, ("low" if undesignated_later else "high")


def resolve_funding_stage(company, funding_rounds, ipo_event) -> str:
    """The FINAL funding_stage with the §B4 v1.14 HUMAN-LOCKED override applied (AUTHORITATIVE over the
    deterministic discriminator — the §B4 analogue of the §B2 floor). A company in
    DOCUMENTED_STAGE_OVERRIDES returns its locked series regardless of the round data (signos / bicycle).
    Every other company (incl. rula, 9amhealth) gets the deterministic discriminator."""
    key = _norm_company(company)
    if key in DOCUMENTED_STAGE_OVERRIDES:
        return DOCUMENTED_STAGE_OVERRIDES[key]
    return funding_stage_from_rounds(funding_rounds, ipo_event)


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
# Funding gate FAIL-SAFE (FRAMEWORK_VERSION v1.2) — a recall miss can read a too-late company as a
# passing early stage. Flag-don't-gate (Rule 7): fire ONLY on ABSENT recent-round PLUS inconsistency,
# never on ABSENT alone (a quiet-but-healthy no-recent-raise company must not be flagged).
# ---------------------------------------------------------------------------

# Conservative DIALS (tune later; near the SOT B4 late-stage dial neighborhood).
FUNDING_FAILSAFE_AGE_YEARS = 7      # an EARLY stage on a company this old is inconsistent
FUNDING_FAILSAFE_COMMERCIAL = 2     # >= moderate (0-3) commercial signal reads as "scaled"
_EARLY_STAGES_FOR_FAILSAFE = frozenset({"pre-seed", "seed", "series-a", "series-b"})


def funding_stage_needs_review(
    funding_stage, recent_round_present, *, company_age_years=None, commercial_signal=None
) -> bool:
    """Gate fail-safe (flag-don't-gate, Rule 7): a funding RECALL miss can read a too-late company as a
    passing EARLY stage. Two routes to review: (req 1, §14) an UNKNOWN / undeterminable mapped stage --
    from ANY cause, incl. the canonical filter excluding every gathered type -- ALWAYS routes to review, so
    the robustness fix can never hide a silent gate pass/fail. Otherwise fire ONLY when the recent round is
    ABSENT (a possible recall miss) AND the early stage is INCONSISTENT with other maturity signals --
    NEVER on ABSENT alone (a quiet-but-healthy company that genuinely hasn't raised recently must NOT be
    flagged for the quiet stretch). The ~24mo presence window (presence check) and the AGE / COMMERCIAL
    thresholds here are DIALS with conservative defaults; the flag only routes to human review -- it never
    gates and never alters the mapped stage."""
    stage = _norm_stage(funding_stage)
    if not stage:                                                   # req 1 (§14): unknown/undeterminable mapper output -> ALWAYS review, never a silent gate pass/fail
        return True
    if _is_true(recent_round_present):                              # a recent round WAS gathered -> no recall-miss risk
        return False
    if stage not in _EARLY_STAGES_FOR_FAILSAFE:                     # only an early stage can FALSE-PASS a too-late co
        return False
    old = company_age_years is not None and company_age_years >= FUNDING_FAILSAFE_AGE_YEARS
    scaled = commercial_signal is not None and commercial_signal >= FUNDING_FAILSAFE_COMMERCIAL
    return bool(old or scaled)                                       # ABSENT + early + (old OR scaled) -> flag for review


def _has_recent_priced_round(funding_rounds, ref_year, *, window_years=2) -> bool:
    """Deterministic proxy for 'a recent priced round was gathered' -- any PRICED EQUITY round dated within
    ~window_years of ref_year. Recomputable from the stored funding_rounds (Rule 7), so the fail-safe's
    recall-miss signal needs no LLM-result persistence (the LLM presence check stays observability-only)."""
    for r in funding_rounds if isinstance(funding_rounds, list) else []:
        if isinstance(r, dict) and _is_true(r.get("is_priced_equity")) and _has_date(r.get("date")):
            year, _month = _parse_date(r.get("date"))
            if year and 0 <= ref_year - year <= window_years:
                return True
    return False


def _rounds_from_json(raw) -> list:
    """Reconstruct funding_rounds from the persisted funding_rounds_json column (or a live list)."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def derive_funding_failsafe(row, *, ref_year) -> bool:
    """Wired gate fail-safe (Rule 7, recomputable from stored columns): reads the persisted
    funding_rounds_json + funding_stage + founding_year and the commercial signal, and applies
    funding_stage_needs_review. The gate / review calls this; it routes to human review, never gates."""
    rounds = _rounds_from_json(row.get("funding_rounds_json"))
    founding_year, _ = _parse_date(row.get("founding_year"))
    age = (ref_year - founding_year) if founding_year else None
    return funding_stage_needs_review(
        row.get("funding_stage"),
        _has_recent_priced_round(rounds, ref_year),
        company_age_years=age,
        commercial_signal=derive_commercial_signal(row),
    )


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


# ---------------------------------------------------------------------------
# Business-model classifier (§B2) — the PATH-gate linchpin (Commit 1).
#
# Built clean from SOT SCORING_FRAMEWORK_SOURCE_OF_TRUTH.md §B2 (FRAMEWORK_VERSION v1.13),
# regression target business_model_classifier_fixture.md (v1.3). Rule 7: the LLM extracts
# who_uses / who_pays (gathers evidence — see research_runner.build_business_model_prompt);
# THIS deterministic mapper emits the B2B / B2B2C / B2C label. The LLM never emits the label.
#
# Two human-authoritative override layers sit ABOVE the mapper (Rule 6 — human decisions take
# precedence over an automated value): the human-locked B2B FLOOR, and the documented spike
# overrides. A forced label ignores the classifier read entirely.
# ---------------------------------------------------------------------------

BUSINESS_MODELS = frozenset({"B2B", "B2C", "B2B2C"})
WHO_USES_VALUES = frozenset({"consumer", "professional"})
WHO_PAYS_VALUES = frozenset({"consumer", "institution", "mixed"})

# Human-locked B2B FLOOR (SOT §B2 v1.4): AUTHORITATIVE over the classifier. For any company
# here, business_model is FORCED to "B2B" regardless of the read, because the classifier cannot
# reliably hold the provider-tool / hospital-at-home-enablement vs own-care-team who_uses
# boundary (medically home oscillated across three tuning rounds). A classifier floor-MISS on a
# listed company is a NON-FAILURE by design — the override catches it. The load-bearing property
# is that the floor fires EVEN WHEN the classifier reads the company consumer (adversarial input).
# MAINTENANCE: adding/removing a floor company is a doc-first edit to SOT §B2, NOT a code change.
LOCKED_B2B_FLOOR = frozenset(
    {"openevidence", "cohere health", "zus health", "om1", "medically home", "linus health"}
)

# Documented spike-era overrides (SOT §B2): forced to their locked-truth label regardless of the read.
# Both remaining entries are proven LOAD-BEARING on the live-54 run (the prompt does NOT fix either):
#   noom med      = minor-channel who_pays over-read (live raw consumer/mixed -> B2B2C; corrected to B2C)
#   counsel health = evidence-thin input gap (live raw consumer/consumer -> B2C; corrected to B2B2C, Rule 8)
# `signos` was RETIRED 2026-06-30: the v1.13 EVIDENCE-ONLY prompt reads it correctly (live raw
# consumer/consumer -> B2C == the override's value, so the override was INERT). A redundant override would
# MASK a future prompt regression on signos, so signos now rides the mapper, where its correctness is
# visible + testable (same principle as the adversarial floor test). See specs/classifier_prompt_flags.md.
# The mapper applies these to the FINAL label; the live classifier's RAW read is still persisted (who_pays)
# so an evidence-thin under-read (e.g. counsel raw=B2C) stays VISIBLE while the final label is the locked truth.
DOCUMENTED_BUSINESS_MODEL_OVERRIDES = {
    "noom med": "B2C",
    "counsel health": "B2B2C",
}

# Persisted Rule-7 columns from the classifier block (raw extraction carried + derived label).
BUSINESS_MODEL_FIELDS = [
    "who_uses",
    "who_uses_basis",
    "who_pays",
    "who_pays_basis",
    "who_uses_confidence",
    "business_model",
    "business_model_needs_review",
]


def _norm_company(value) -> str:
    """Company key for floor / override lookups: trimmed lowercase, whitespace collapsed."""
    return re.sub(r"\s+", " ", _norm(value))


def map_business_model(who_uses, who_pays) -> str:
    """The LOCKED §B2 mapper (who_uses / who_pays -> label); the LLM never emits the label.

        professional                 -> "B2B"     # PATH Test A floor, regardless of who_pays
        consumer + consumer-pays     -> "B2C"
        consumer + institution/mixed -> "B2B2C"

    A consumer user with an unrecognized / undeterminable who_pays returns "" so the caller can
    flag for review rather than silently guess a label (Rule 8 — absence isn't filled in)."""
    wu = _norm_enum(who_uses)
    wp = _norm_enum(who_pays)
    if wu == "professional":
        return "B2B"
    if wp == "consumer":
        return "B2C"
    if wp in ("institution", "mixed"):
        return "B2B2C"
    return ""


def business_model_for(company, who_uses, who_pays, who_uses_confidence=None) -> tuple[str, bool]:
    """Resolve the FINAL business_model + needs_review for one company (Rule 6/7 precedence).

    Order, highest precedence first:
      1. human-locked B2B FLOOR    -> "B2B"  (forced; the classifier read is ignored)
      2. documented spike override -> its locked label (forced)
      3. the §B2 mapper on the classifier's who_uses / who_pays read

    needs_review fires ONLY on a NON-forced company that is either undeterminable (mapper -> "")
    or carries who_uses_confidence == "low" (flag, don't gate — SOT §B2). A forced company needs
    no review: the human already decided, so confidence is moot."""
    key = _norm_company(company)
    if key in LOCKED_B2B_FLOOR:
        return "B2B", False
    if key in DOCUMENTED_BUSINESS_MODEL_OVERRIDES:
        return DOCUMENTED_BUSINESS_MODEL_OVERRIDES[key], False
    label = map_business_model(who_uses, who_pays)
    needs_review = label == "" or _norm_enum(who_uses_confidence) == "low"
    return label, needs_review


def flatten_business_model_fields(parsed, *, company=None) -> dict:
    """Flatten the classifier block into persisted Rule-7 columns: the RAW who_uses / who_pays
    extraction (carried, recomputable) PLUS the derived business_model (mapper / floor / override).
    The raw read is preserved even when an override forces a different final label, so an
    evidence-thin or floor-missed read stays auditable. Tolerant of a missing / non-dict block.

    Reads ``parsed["business_model_classifier"]`` (the LLM JSON object) and the company (passed in
    or ``parsed["company"]``)."""
    block = parsed.get("business_model_classifier") if isinstance(parsed, dict) else None
    block = block if isinstance(block, dict) else {}
    co = company if company is not None else (parsed.get("company") if isinstance(parsed, dict) else "")
    who_uses = _norm_enum(block.get("who_uses"))
    who_pays = _norm_enum(block.get("who_pays"))
    confidence = _norm_enum(block.get("who_uses_confidence"))
    label, needs_review = business_model_for(co, who_uses, who_pays, confidence)
    return {
        "who_uses": who_uses,
        "who_uses_basis": _safe_text(block.get("who_uses_basis", "")),
        "who_pays": who_pays,
        "who_pays_basis": _safe_text(block.get("who_pays_basis", "")),
        "who_uses_confidence": confidence,
        "business_model": label,
        "business_model_needs_review": needs_review,
    }


# ---------------------------------------------------------------------------
# PATH-TO-SCALE gate (§B3) — Commit 2. Runs on the Commit-1 classifier output + evidence.
#
# Built clean from SOT §B2/§B3 (FRAMEWORK_VERSION v1.13), logic-faithful to the spike
# (spike_scoring_spine.py path_gate). Two sequential tests:
#   Test A  is there a consumer end-user?  business_model == "B2B" -> GATE_FAIL (no consumer).
#   Test B  is the engine viable? (loose "engine alive" floor ONLY — strength is PMF's job, B1):
#             B2C   -> alive if revenue OR meaningful user-scale OR positive growth (no-revenue
#                      fallback ^c10: missing revenue != dead).
#             B2B2C -> pass iff a REAL durable institutional channel exists.
#
# EMPLOYER-DIRECT SCOPE FIX (§B3, the Function Health gap): the institutional-channel check
# covers EMPLOYER-DIRECT (e.g. "Function for Work"), not payer-reimbursed only — an insurance-free
# employer channel is still a real B2B2C channel. The check stays a LOOSE floor (real customers /
# covered lives / scaled adoption), NOT pilots/positioning.
# ---------------------------------------------------------------------------

# Robust "$ figure present ANYWHERE in the text" detector (findings lead with hedges like
# "No company-reported ARR, but Sacra estimates $100M" — a prefix check false-floors them).
_DOLLAR_FIGURE_RE = re.compile(r"\$\s*[\d.]+\s*(?:k|m|b|million|billion)\b", re.I)
_PLAIN_MAGNITUDE_RE = re.compile(r"\b\d[\d,]*\s*(?:k|m|million|billion)\b", re.I)
_GROWTH_PCT_RE = re.compile(r"\d+\s*%")
_NAMED_PAYER_RE = re.compile(
    r"aetna|blue cross|bcbs|anthem|unitedhealth|\buhc\b|cigna|oscar|humana|medicaid|medicare|"
    r"\bcms\b|commonspirit|essence|baptist",
    re.I,
)
_INSTITUTIONAL_STRUCTURAL_RE = re.compile(
    r"covered lives|in-?network|\d[\d,]*\s*(?:members|covered|lives)\b", re.I
)
_EMPLOYER_DIRECT_KEYS = ("partner", "client", "benefit", "self-insured", "for work", "sponsored", "funds")
_HEALTH_PLAN_KEYS = ("partner", "contract", "client", "relationship")


def _row_get(row, key) -> str:
    """Read a column from a dict / pandas-Series row, tolerant of missing key / NaN / None -> ''."""
    try:
        value = row.get(key, "")
    except AttributeError:
        value = ""
    return _safe_text(value)


def _has_money_figure(text) -> bool:
    t = _norm(text)
    return bool(_DOLLAR_FIGURE_RE.search(t)) or bool(_PLAIN_MAGNITUDE_RE.search(t))


def has_any_revenue(row) -> bool:
    """A revenue/ARR figure present anywhere in revenue_or_arr (company-reported OR estimated)."""
    return _has_money_figure(_row_get(row, "revenue_or_arr"))


def has_meaningful_user_scale(row) -> bool:
    """A real user/customer-scale figure: sponsored_user_scale OR paying_customer_count."""
    return _has_money_figure(_row_get(row, "sponsored_user_scale")) or _has_money_figure(
        _row_get(row, "paying_customer_count")
    )


def has_positive_growth_signal(row) -> bool:
    """A POSITIVE growth signal present (loose gate presence check only — strength is scored in PMF).
    A 'declining' signal does not count."""
    g = _norm(_row_get(row, "growth_signal"))
    if not g or "declin" in g:
        return False
    return (
        "grow" in g
        or bool(_GROWTH_PCT_RE.search(g))
        or "x over" in g
        or "tripl" in g
        or "doubl" in g
    )


def has_real_institutional_channel(row) -> bool:
    """A REAL durable institutional/B2B2C channel (named payers / covered lives / scaled employer
    or health-plan relationship / value-based contract), NOT pilots/positioning. Covers EMPLOYER-
    DIRECT, not payer-reimbursed only (§B3 scope fix — the Function Health gap). Reads the
    payer_institutional_finding + business_model_type evidence."""
    blob = _norm(_row_get(row, "payer_institutional_finding") + " " + _row_get(row, "business_model_type"))
    if _NAMED_PAYER_RE.search(blob) or _INSTITUTIONAL_STRUCTURAL_RE.search(blob):
        return True
    if "employer" in blob and any(k in blob for k in _EMPLOYER_DIRECT_KEYS):
        return True  # employer-direct channel (insurance-free) still counts (the scope fix)
    if "health plan" in blob and any(k in blob for k in _HEALTH_PLAN_KEYS):
        return True
    return "value-based" in blob or "outcomes-based contract" in blob


def path_gate(business_model, row) -> tuple[bool, str]:
    """The §B3 PATH-to-scale gate. Returns ``(passed, reason)``.

    Test A — B2B floor: business_model == "B2B" -> FAIL (no consumer end-user; the locked floor
    companies fail here via the Commit-1 override). Test B — engine-alive (loose floor): B2C alive
    on revenue OR user-scale OR positive growth; B2B2C alive on a real institutional channel. An
    unmapped / empty business_model -> FAIL (do not silently pass an undeterminable company)."""
    bm = _safe_text(business_model).upper()
    if bm == "B2B":
        return False, "Test A: B2B floor — no consumer end-user"
    if bm == "B2C":
        if has_any_revenue(row) or has_meaningful_user_scale(row) or has_positive_growth_signal(row):
            return True, "Test B (B2C): engine alive — revenue / user-scale / growth"
        return False, "Test B (B2C): DEAD — no revenue, user-scale, or growth signal"
    if bm == "B2B2C":
        if has_real_institutional_channel(row):
            return True, "Test B (B2B2C): real institutional channel"
        return False, "Test B (B2B2C): no real institutional channel"
    return False, f"unmapped business_model: {business_model!r}"


# ---------------------------------------------------------------------------
# AGENCY gate (§B4) — Commit 3c. Deterministic from funding_stage + reset.
#
# Built clean from SOT §B4 (v1.10/v1.13), logic-faithful to the spike agency_gate. Maturity is FACTUAL
# only (funding stage); the LLM never adds a parallel "timing" judgment (B1). Reset (the deterministic
# derive_reset_signal — type ∈ FIREABLE AND opening=="yes") flips a maturity FAIL -> PASS for a mature
# company whose build-window reopened. The funding_stage passed in should be the RESOLVED stage
# (resolve_funding_stage — override applied) so the §B4 v1.14 lock is honored.
# ---------------------------------------------------------------------------

def agency_gate(funding_stage, reset_fired, *, ipo_status=None) -> tuple[bool, str, bool]:
    """The §B4 AGENCY maturity gate. Returns ``(passed, reason, late_c_flag)``.

      public / pre-IPO / series-d-plus  -> PASS iff reset fired, else FAIL (too-late unless reopened)
      seed / pre-seed                   -> FAIL (too-early — reset does NOT rescue a not-yet-open window)
      series-a / series-b / series-c    -> PASS

    ``late_c_flag`` exposes the OPEN-DIAL (series-c is a clean PASS in this build; calibration can switch
    it to a soft pass that lowers the score). An unknown / undeterminable stage -> FAIL (never a silent
    pass)."""
    stage = _norm_stage(funding_stage)
    ipo = _norm_enum(ipo_status)
    rf = bool(reset_fired)
    late_c = stage == "series-c"
    if ipo == "public" or stage == "public":
        return rf, f"public/{stage or '?'} mature" + (" +reset" if rf else " (no reset)"), late_c
    if stage == "series-d-plus":
        return rf, f"{stage} late-stage" + (" +reset" if rf else " (no reset)"), late_c
    if stage in ("seed", "pre-seed"):
        return False, f"{stage} too-early (no reset rescue)", late_c
    if stage in ("series-a", "series-b", "series-c"):
        return True, f"{stage} -> PASS" + (" [late-C clean-pass, dial]" if late_c else ""), late_c
    return False, f"{stage or 'unknown'} undeterminable", late_c
