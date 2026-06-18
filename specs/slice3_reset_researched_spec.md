# Slice 3 — Reset/Restructure as a Researched Field

Builds the automated producer for the reset signal, which currently does not exist.
After Commit A the engine reads the stored `reset_or_restructure_signal` field instead of
the retired text-scan — but nothing populates that field except manual entry, so on fresh
data reset is a dead input. This slice makes reset a RESEARCHED field, and — critically —
distinguishes a genuine reset OPENING from a strategic pivot or defensive change that only
looks similar (the Noom problem).

## Core principle: reset = a high-agency ENTRY OPENING, not a business/health signal

The reset exception exists to flag a moment of organizational disruption that creates
WHITESPACE and a forward-looking MANDATE for a senior operator to build. It is a signal
about OPERATOR OPPORTUNITY, not about company strategy or health.

- ZOE (new leadership / turnaround creating a builder mandate) -> reset fires.
- Noom (D2C->payer pivot under competitive pressure, struggling) -> reset does NOT fire.
  A defensive pivot is the opposite of a high-agency opening.

The distinguishing test is forward-looking mandate vs. defensive reaction:
- Reset opening = the company is actively REBUILDING / TRANSFORMING and needs senior
  operators to do it (a forward mandate exists).
- Not a reset = the company is reacting defensively (pivot, contraction-toward-decline,
  routine integration) — no builder mandate.

## LLM researches and returns (persisted as columns):
- `reset_event_type` — none | leadership-change | declared-transformation |
  founder-transition | post-failure-rebuild | restructuring-layoffs | strategic-pivot |
  ma-integration
- `reset_basis` — evidence/source text for whatever was found
- `reset_creates_high_agency_opening` — the POINTED question: yes | no | unclear.
  "Does this event create a forward-looking mandate for a senior operator to build,
  versus a defensive reaction?"

## Deterministic reset rule (reads the stored fields):
```
reset_signal = TRUE  iff  reset_creates_high_agency_opening == "yes"
                          AND reset_event_type NOT IN {strategic-pivot, ma-integration}
otherwise FALSE
```

Key rules:
- `strategic-pivot` and `ma-integration` NEVER fire reset — they are not openings.
  (M&A integration is also the source of the retired text-scan's "integration" false positive.)
- `restructuring-layoffs` is AMBIGUOUS and does NOT get a fixed bucket — it routes through
  the `reset_creates_high_agency_opening` question like any other event. Painful-but-
  necessary restructuring toward a rebuild (chaos a strong operator can enter) -> yes ->
  fires. Contraction toward survival/decline -> no -> does not fire. The OPENING question
  decides, not the event label.
- The pointed question is what carries the judgment; the event type mostly just excludes the
  two never-fire types and provides context.

## Strategic pivots: recorded as context, NOT a scoring input
When a strategic pivot is found (Noom-type), it is RECORDED (reset_event_type =
strategic-pivot, reset_basis = the evidence) so it's visible on the dashboard — but it is
NOT wired as its own scoring input, because its scoring effect is ALREADY captured by the
current-state commercial and institutional signals (a D2C->payer pivot shows up as the
institutional signal rising and the D2C/commercial signal reflecting the struggle). Wiring
the pivot in separately would DOUBLE-COUNT it. The pivot explains WHY the signals look as
they do; it is not an independent factor on top.

(Deferred / not built now: a "signals may be in transition" caution flag for very recent
pivots, where snapshot signals are mid-transition and trajectory matters more than current
state. Recordable later from the stored context if it proves needed — not speculative
machinery now.)

## Manual override: not needed for reset
No reset-specific manual override. The priority-level manual override already exists; if a
reset judgment produces a wrong priority, it can be corrected there directly.

## Retire
- The text-scan reset markers were already retired in Commit A. This slice replaces the
  manual-only population of `reset_or_restructure_signal` with the researched fields above
  and the deterministic rule.

## Build notes
- Add the three reset fields to the fit-brief prompt (`run_company_fit_brief`) — the single
  insertion point feeding both STEP 7 (fresh) and STEP 26 (rescore).
- Parse in the STEP 10 flatten; persist as master columns.
- The deterministic reset rule should be a package function (testable, red->green), reading
  the stored fields. The engine's existing `reset_signal(row)` (post-Commit-A) should read
  the derived signal.
- Tests: ZOE-type (leadership-change/transformation + opening=yes) -> fires; Noom-type
  (strategic-pivot) -> does NOT fire even if it looks disruptive; restructuring-layoffs +
  opening=yes -> fires, + opening=no -> does not; ma-integration -> never fires.
