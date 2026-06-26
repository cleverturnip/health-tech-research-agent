# Growth-rate: stop-on-hit is OUT. Refine-to-derive first, re-measure, then size N (always-run, never stop-on-hit). Plus paying-count enable + findings capture + Group 2.

Clean re-measure — and it caught a wrong N before the regen (Correction 1 earning its keep again).
Decisions below.

## paying-count — ENABLE at N=5 (clean, done)
Worst-case Function 40% → N=5 gives ~92%. Tightening 2 VALIDATED — the Pelago stress case kept paying
employer-clients distinct from covered/eligible lives across every pass (and recovered them from
Pelago's own press releases, not aggregators — lead-not-filter working). Enable paying-count config at
N=5. No wording changes needed.

## growth-rate — stop-on-hit REJECTED. Here's the strategy.

### Why NOT stop-on-hit (the decision)
Growth is 60% of PMF — the single heaviest input to the score. Stop-on-hit grabs the FIRST usable rate
found, so the number driving most of a company's PMF would be set by WHICH PASS HIT FIRST — and given
the variability (Midi 20%, rates blinking pass-to-pass), the first hit is often a weaker source when a
later pass would surface the company-disclosed rate. That lets luck pick the most important signal. We
want the BEST rate, not the FIRST rate. Stop-on-hit is out.

### The real finding: growth rates are RAW MATERIAL more than stated rates
Pelago hit 5/5 because "287% in 2023" is pre-computed and clean. Midi hit 20% because its rate must be
DERIVED from "$60M end-2024 -> $150M late-2025" — and the current prompt asks for STATED rates, not
derivation. So the variability is partly an artifact of the prompt looking for the harder-to-find form.
That means the fix is to attack variability at its SOURCE (derive), not to throw more passes at a
prompt asking for the wrong thing.

### STEP 1 (primary fix) — refine-to-derive. Bring me the wording.
Refine the growth-rate prompt to DERIVE the rate from dated revenue endpoints the search already finds
(Latka's "$0 2021 -> $115.9M 2025"; Midi's "$60M end-2024 -> $150M late-2025"). REQUIREMENTS for the
wording:
- Instruct the model to COMPUTE a rate when it finds two or more dated revenue points, not only to
  report pre-stated rates.
- MANDATORY show-the-inputs: a derived rate MUST display its inputs and period alongside it — e.g.
  "~2.5x over ~9mo, computed from $60M (Dec 2024) -> $150M (Sep 2025)", NOT a bare "150% growth". A
  computed rate with no visible inputs recreates the uninterpretable-figure problem one level up, so
  inputs+dates are required, not optional.
- Keep Tightening 1: any rate (stated or derived) is only usable WITH its period; flag "period
  unclear" / "endpoints found, dates missing — not usable" rather than emitting a dateless rate.
- Keep lead-not-filter + alias handling from the approved version.
This is LLM-facing → bring the wording for my review before building.

### STEP 2 — re-measure Midi/Solace/ZOE AFTER the derive fix
Derive may dissolve the N problem: if it lifts Midi/Solace/ZOE from 20-40% toward Pelago's reliability
(plausible — their rates ARE derivable from points the search finds), growth lands at N=5 like paying-
count and we're done. Re-measure to find out.

### STEP 3 — set N against the IMPROVED hit rate. If still variable: ALWAYS-RUN-N, never stop-on-hit.
- If derive gets the worst case to a healthy hit rate → N=5 (or whatever the re-measure shows), same
  as the other fields.
- If growth is STILL variable after derive → use ALWAYS-RUN-N sized to the re-measured rate, NOT
  stop-on-hit. Corroboration on the 60%-of-PMF signal is worth the passes; first-hit luck on it is not
  acceptable. (Do NOT take N=11 to the regen as a reflex — size it to the post-derive rate.)
- N is per-field config; growth can use a different N than revenue's 5.

### The floor (de-risks all of this)
PMF already falls back to qualitative growth_signal (growing/flat/declining) when no usable rate is
found — so a missed rate degrades to a less-precise score, it does NOT blank the field. We're
optimizing growth-rate for PRECISION on the most important signal, not to avoid a hole. That's why
real effort is justified (60% of PMF) but a desperate 11-pass spend is not (the floor catches misses).

## Capture the re-measure durably (now, separate from wording)
Append to the probe findings doc: real per-field N (paying-count=5; growth-rate pending post-derive),
the growth-rate-is-raw-material finding, Tightening 2 validated (Pelago paying vs covered-lives),
and the redundancy result (fields diverge — growth leans Latka, paying leans company press; only CB
Insights overlaps → consolidation lever real but modest, logged no change). Commit it.

## Group 2 (valuation + rev-per-user) — bring wording in parallel, BUT flag the stakes
Bring Group 2 wording in parallel with growth-rate's derive wording (they're independent). BUT: valuation
and rev-per-user feed the model LESS directly than revenue/growth. Before applying the full derive-level
rigor, give me your read — do these genuinely need the same treatment, or can they be enabled more
lightly (e.g. simpler source-directed prompt, lower N, accept the qualitative floor)? Don't reflexively
give them the full process growth-rate just needed; match the rigor to the stakes.

## Sequence / discipline
Capture findings (now) → enable paying-count N=5 → bring growth-rate refine-to-derive wording + Group 2
wording for joint review → I approve → build + re-measure growth-rate (derive) → set growth N (always-
run, not stop-on-hit) → enable Group 2 per its stakes → then set permanent per-field N → THEN the one
run-once regen. LLM-facing wording stays joint; still local (no push/PR); Function-payer scope parked
for the PATH gate.
