# Slice 3 Addendum — Multi-Event Reset (per-event opening evaluation)

## Why this addendum exists (the ZOE finding)

Slice 3's live Colab verification surfaced a structural gap. ZOE is simultaneously:
- doing a STRATEGIC PIVOT (premium at-home testing -> mass-market freemium platform: ZOE 2.0
  app, halved prices, Daily30+), AND
- doing a RESTRUCTURING-toward-expansion (team restructurings + cost reductions "to achieve
  rapid expansion" — growing-pains restructuring, not a death-spiral contraction).

The original Slice 3 design used a SINGLE `reset_event_type` and a SINGLE company-level
opening question. Result: the LLM saw the dominant pivot story, typed ZOE as a pivot/none,
and the coexisting restructuring — which is exactly the "necessary restructuring / chaos a
strong operator can enter" case the opening question was meant to catch — got buried. Reset
returned False when ZOE may be a genuine opening.

Diagnosis: not a logic bug and not a one-company fluke — a STRUCTURAL gap. A company can have
multiple coexisting reset events of different kinds, and a single-value field forces the
louder signal to win, hiding the one that should fire. Decision: fix it structurally before
the run-once regeneration (the pattern is "occasional" but a silent under-fire on
turnaround-chaos companies, in a non-repeatable regeneration, is worth the fix).

## The fix: per-event opening evaluation (Design 2)

`reset_event` becomes a LIST of event objects; each event carries its OWN opening assessment,
so a pivot's "no" cannot bury a restructuring's "yes". They are evaluated independently.

### LLM returns (replaces the single-value reset_evidence block):
```
"reset_evidence": {{
  "reset_events": [
    {{
      "event_type": "leadership-change / declared-transformation / founder-transition / post-failure-rebuild / restructuring-layoffs / strategic-pivot / ma-integration",
      "basis": "source + date for THIS event",
      "creates_high_agency_opening": "yes / no / unclear"   // evaluated for THIS event specifically
    }}
    // ... one object per distinct event found; empty list if none
  ]
}},
```
- If no reset/restructure events are found, `reset_events` is an empty list `[]` (the "none"
  case is now the empty list, not an event type — see note below).
- Each event is assessed on ITS OWN terms: for ZOE, the strategic-pivot event gets
  creates_high_agency_opening per its own nature (and is never-fire anyway), while the
  restructuring-layoffs event gets its own opening answer independent of the pivot.

### Prompt instruction changes (keep the Slice 3 framing, apply per-event):
- Keep the reset-vs-pivot framing, the restructuring-layoffs "do not prejudge" rule, and the
  strategic-pivot-vs-declared-transformation strengthening — but instruct the LLM to LIST
  EACH distinct event separately and answer the opening question PER EVENT.
- Explicit instruction: "A company may be doing several of these at once (e.g. pivoting its
  model AND restructuring its team). List each as a separate event with its own opening
  answer. Do NOT let one event's nature determine another's — a strategic pivot does not make
  a coexisting restructuring an opening, and a pivot does not hide a restructuring that IS an
  opening."

### Deterministic rule (replaces single-value derive_reset_signal):
```
RESET_NEVER_FIRE = {strategic-pivot, ma-integration}   # note: "none" is no longer a type;
                                                        # empty list handles the no-event case
derive_reset_signal(reset_evidence) -> bool:
    events = reset_evidence.get("reset_events", [])
    if not events:                      # empty list -> no event -> False
        return False
    for ev in events:
        etype  = norm(ev.event_type)
        opening = norm(ev.creates_high_agency_opening)
        if etype not in RESET_NEVER_FIRE and opening == "yes":
            return True                 # ANY non-never-fire event with opening=yes fires
    return False
```
- Fires iff AT LEAST ONE event is (not in never-fire) AND (opening == yes).
- ZOE: [strategic-pivot(opening=no, never-fire anyway), restructuring-layoffs(opening=yes)]
  -> the restructuring event fires -> True. The pivot can no longer bury it.
- Noom: [strategic-pivot(opening=no)] -> never-fire + no -> False. Unchanged, still prevented.

### Flag-2 (none) handling under the list model
The incoherent "none + opening=yes" case is now structurally impossible a different way: there
is no "none" event type — absence of events is the empty list, which returns False before any
opening is read. So the Flag-2 protection is preserved (arguably cleaner). Keep
strategic-pivot and ma-integration in RESET_NEVER_FIRE.

## Persistence (richer dashboard record — a Design 2 benefit)
Persist the per-event detail, not just the final bool. Recommended columns:
- `reset_or_restructure_signal` (derived bool — what the engine reads; unchanged contract)
- `reset_or_restructure_basis` (basis of the FIRING event if one fired, else the most salient
  event's basis, else empty)
- `reset_events_json` (the full list, persisted so the dashboard can show "pivoting AND
  restructuring; the restructuring is the opening" — and so it's recomputable without
  re-research, per the Part C principle)
- Optionally flat helper columns (e.g. `reset_event_types` as a comma-joined list) for easy
  scanning, derived from the json.

## What stays the same
- The engine (`candidate_priority.reset_signal`) still reads `reset_or_restructure_signal` —
  no engine change; the derivation just produces it from the list now.
- Strategic pivots are still RECORDED (now as an event in the list) but never fire and add no
  separate scoring input — their effect is already in the commercial/institutional signals.
- restructuring-layoffs still rides the opening question (now per-event).
- No STEP 26 change.

## Tests (red->green) — extend the Slice 3 suite
- ZOE multi-event: [strategic-pivot/no, restructuring-layoffs/yes] -> fires. RED PROOF: a
  single-event/single-opening variant (the old design) returns False -> caught. This is THE
  proof for this addendum (the buried-restructuring case now fires).
- Noom: [strategic-pivot/yes] -> never fires (unchanged).
- Empty list -> False (the old "none" case).
- Multiple never-fire events only ([strategic-pivot/yes, ma-integration/yes]) -> False.
- A non-never-fire event with opening=no among others -> doesn't fire unless another fires.
- Mixed: [strategic-pivot/no, leadership-change/yes] -> fires (leadership-change).
- flatten handles the list (variable length, empty, non-dict-tolerant); reset_events_json
  round-trips.

## Build note
This reopens Slice 3's prompt + derivation (Commits like 2 & 4 of the original slice) since
the field shape changed from single-value to a list. Re-verify in Colab on a multi-event
company (ZOE is the natural test — it should now fire on the restructuring). The prompt->parse
seam is more complex (variable-length list of objects), so the Colab check that the list
actually populates from real LLM output matters more here than in the single-value version.
