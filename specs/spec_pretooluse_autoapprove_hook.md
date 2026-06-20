# Spec — Claude Code `PreToolUse` Hook: Auto-Approve Read-Only Bash

> **Purpose of this file:** A self-contained spec for a Claude Code `PreToolUse` hook that
> eliminates constant approval prompts for read-only/diagnostic bash commands, while keeping
> every state-changing or destructive command in front of the user. Written so a NEW chat
> (with no memory of the conversation that produced it) can pick it up, finish the design with
> Katelynd, and hand a reviewed script to Claude Code to build. Nothing here has been built yet.

---

## 0. Status / how to pick this up
- **Not started.** This is design-only. No hook script exists yet.
- This is a **side task**, parked while the Slice 3.7 search-layer build is in flight. It is
  independent of the research-agent code and touches only Claude Code's own configuration
  (`.claude/settings.json` + a hook script). It does NOT touch the
  `health_tech_research_agent` package.
- **Before building:** confirm the hook schema below against the current Claude Code docs
  (https://code.claude.com/docs/en/hooks) — the schema was verified ~June 2026 but Claude Code
  hooks change fast. Also confirm Claude Code version ≥ 1.0.20 (`claude --version`); hooks were
  introduced then.
- **Workflow reminder (Katelynd's standing model):** design/decide in chat with Claude; hand the
  finished, reviewed script to Claude Code to build. The hook script itself is the
  highest-stakes artifact here because it runs with shell privileges — design it together, do
  not let it be written unreviewed.

---

## 1. The problem (with real evidence)
While Claude Code runs a multi-step task, it pauses for manual approval on nearly every bash
command. Choosing "always approve" in the UI does not stop the prompts, because approvals are
matched per-command-pattern and Claude Code's commands are **chained and piped**
(`cd … && echo … && python3 … | tail`, with `2>&1`), which the simple allow-pattern matcher in
`settings.json` does not reliably match. The result is approval fatigue: the user must babysit
the run, and the reflexive "yes" is itself a risk (a known failure mode — see §6).

### 1.1 Real command corpus (the test set the hook must satisfy)
Nine real approval prompts captured from live Slice 3.7 sessions. These are the regression
fixtures — the finished hook should be checked against all nine.

**Group A — pure inspection / diagnostics (SHOULD AUTO-APPROVE):**
1. `cd <repo> && echo "…" && PYTHONPATH=src python3 -m pytest tests/test_research_runner.py -k "…" -q 2>&1 | tail -20`
2. `cd <repo> && which python3 pytest 2>&1; echo "---"; python3 -c "import health_tech_research_agent.research_runner as rr; print(...)" 2>&1 | tail -5`
3. `cd <repo> && ls -d .venv venv env .env 2>/dev/null; find . -maxdepth 2 -name "pyvenv.cfg"; python3 -m pytest --version; python3 -m pip show health-tech-research-agent`
4. `cd <repo> && grep -nE "pythonpath|testpaths|…" pyproject.toml; ls conftest.py tests/conftest.py; python3 -m pytest … -q 2>&1 | tail -25`
5. `cd <repo> && PYTHONPATH=src python3 -c "import …; print('import OK …')"; PYTHONPATH=src python3 -m pytest … -q 2>&1 | tail -15`
6. `cd <repo> && grep -nE "REQUIRED_RESEARCH_COLUMNS" src/…/research_runner.py; grep -nE "Latest research findings|reset_evidence|…" src/…/research_runner.py | sed -n '1,40p'`
7. `cd <repo> && grep -nE "class BatchClient|def .*search|…" tests/test_research_runner.py | sed -n '1,30p'; grep -rnE "REQUIRED_RESEARCH_COLUMNS|…_finding" tests/ | sed -n '1,40p'`

**Group B — bundles a state-changing clause (MUST ASK, never auto-approve):**
8. `cd <repo> && PYTHONPATH=src python3 -m pytest … -q 2>&1 | tail -6; echo "…"; git add <files>; git commit -q --amend -m "…" -m "…" …; git log --oneline -1`
   — **This is the load-bearing example.** It glues a safe `pytest` to `git add` + `git commit
   --amend`. A "does this contain anything read-only?" rule would wrongly pass it. The presence
   of `git commit --amend` must force ASK.

(Group A item count = 7, Group B = 1; the 9th captured example was an earlier variant of #1.
Treat the corpus as "7 auto-approve, ≥1 ask" — the exact count matters less than coverage of
the verb shapes.)

---

## 2. Goal / non-goals
**Goal:** Auto-approve bash commands whose **every** clause is read-only, so diagnostic/inspection
runs (grep, ls, find, cat, which, `python3 -c`, `pytest`, `pip show`, `git status|diff|log|show`)
proceed without prompting. Everything else continues to prompt exactly as today.

**Non-goals:**
- NOT a replacement for human review of commits, edits, pushes, installs, or deletions. Those
  must keep prompting.
- NOT `--dangerously-skip-permissions`. That flag is explicitly rejected for this repo (master
  data in Drive + an expensive run-once regeneration make unwatched destructive commands too
  costly).
- NOT a security sandbox. The hook reduces approval fatigue; it is not a containment boundary.

---

## 3. Core design rule (the decision logic)
The hook receives the full command string and must classify it. The rule, stated precisely:

> **Auto-approve (`allow`) only if EVERY clause in the command is read-only.**
> **If ANY clause is state-changing or destructive → `ask` (fall through to the user).**
> **Never `deny` from the hook** — denial is the job of the independent settings.json deny
> layer (§5), so the hook can't accidentally become the only thing standing between Claude Code
> and a blocked-but-wanted command. (Keep hook logic to allow-or-defer; let deny rules deny.)

"Clause" = the command split on shell separators: `&&`, `||`, `;`, and pipes `|`. The classifier
must inspect each clause's **leading verb** (after stripping leading `cd`, env-var prefixes like
`PYTHONPATH=src`, and whitespace).

### 3.1 Read-only verb allowlist (every clause must match one)
`cd`, `echo`, `ls`, `pwd`, `cat`, `head`, `tail`, `wc`, `grep`, `rg`, `find`, `sed -n` (print-only
— see §3.3), `awk` (print-only), `which`, `type`, `file`, `tree`, `sort`, `uniq`, `diff`,
`column`, `tr` (in a pipe), `python3 -c` / `python -c`, `python3 -m pytest` / `pytest`,
`python3 -m pip show` / `pip show`, `python3 --version` / `pytest --version` / similar
`--version`/`--help` probes, and the read-only git subcommands:
`git status`, `git log`, `git diff`, `git show`, `git branch` (no `-d`/`-D`/`-m`), `git remote -v`,
`git ls-files`, `git rev-parse`, `git cat-file`.

### 3.2 State-changing / destructive verbs → force ASK (any one present anywhere)
`git add`, `git commit`, `git commit --amend`, `git push`, `git pull`, `git merge`, `git rebase`,
`git reset`, `git checkout`, `git restore`, `git stash`, `git clean`, `git branch -d/-D/-m`,
`git tag`, `git cherry-pick`, `rm`, `rmdir`, `mv`, `cp`, `mkdir`, `touch`, `chmod`, `chown`,
`ln`, `pip install` / `pip uninstall` / `python3 -m pip install`, `npm install` / `npm i`,
`curl`, `wget`, `ssh`, `scp`, any **redirect to a real file** (`>`, `>>`) — note `2>&1` and
`2>/dev/null` are NOT file-writing redirects and must NOT trip this (they appear all over Group A;
the classifier must distinguish stderr-merge/devnull from real-file writes), and any clause whose
leading verb is not in the §3.1 allowlist (default-to-ask on unknown verbs).

### 3.3 Known sharp edges to handle explicitly (design these, don't gloss)
- **`pytest` and `python3 -c` run arbitrary code.** Strictly they are not "read-only." For this
  repo they are treated as auto-approvable because the test suite does not mutate the repo, push,
  or install — and the §5 deny layer means even a surprising test can't push or hard-reset.
  **This is a deliberate judgment call; flag it to Katelynd at build time, don't silently bake
  it in.** If she wants to be stricter, `pytest`/`-c` move to the ask list.
- **Redirect detection:** `2>&1`, `2>/dev/null`, `1>&2`, `&>/dev/null` are stream redirects and
  must be allowed; `> file`, `>> file`, `| tee file` write files and must force ask. The regex
  must not confuse them. (Group A is full of `2>&1`/`2>/dev/null` — getting this wrong breaks
  the whole point.)
- **`sed`/`awk`:** allow only print/inspection forms (`sed -n …p`, `awk '{print …}'`). `sed -i`
  (in-place edit) must force ask.
- **`find … -delete` / `find … -exec rm`:** `find` is allowlisted, but a `find` carrying
  `-delete` or `-exec rm`/`-exec mv` etc. must force ask. Scan find's arguments, not just its verb.
- **Subshells / command substitution** (`$( … )`, backticks): if present, inspect the inner
  command too, or — simpler and safer — force ask whenever substitution is detected. Recommend
  the simpler path for v1.
- **`git commit --amend` (Group B #8):** must force ask. This is the canonical "bundled safe +
  unsafe" case the rule exists for.

---

## 4. Mechanism (verified ~June 2026 — RE-VERIFY before building)
- Hook type: **`PreToolUse`**, matcher `Bash`. Registered in `.claude/settings.json` under
  `hooks.PreToolUse`.
- **Input (stdin, JSON):** includes `tool_name` (`"Bash"`) and `tool_input.command` (the full
  command string). Also `session_id`, `cwd`, `permission_mode`, `hook_event_name`.
- **Output (stdout, JSON):**
  ```json
  { "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow" | "ask" | "deny",
      "permissionDecisionReason": "string"
  } }
  ```
  This hook emits only `allow` or `ask` (per §3; never `deny`).
- **Safety property to rely on:** a `PreToolUse` hook runs *before* the permission prompt and can
  allow / force-ask / deny, **but a hook decision never bypasses a settings.json `deny` or `ask`
  rule.** So the deny list in §5 is an independent backstop the hook cannot accidentally weaken.
- Exit-code note: exit 2 blocks a call (stderr → Claude); for this hook the JSON
  `permissionDecision` is the primary channel. Confirm current exit-code vs JSON semantics in docs.

---

## 5. Independent backstop — settings.json deny rules (build these TOO)
The hook is the convenience layer. These deny rules are the safety layer, and they hold even if
the hook has a bug (deny > ask > allow; hook output can't override deny). Put in
`.claude/settings.json`:
```jsonc
{
  "permissions": {
    "deny": [
      "Read(.env)", "Read(.env.*)", "Read(**/secrets/**)",
      "Bash(rm:*)",
      "Bash(git push:*)",
      "Bash(git reset --hard:*)",
      "Bash(git clean:*)",
      "Bash(curl:*)", "Bash(wget:*)"
    ]
  }
}
```
Rationale for treating deny as non-negotiable: in Dec 2025 a documented incident had Claude Code
generate `rm -rf … ~/` during a "clean up the repo" task, wiping a home directory. The deny layer
exists for exactly that class of accident, independent of how good the hook's parsing is.

(If Katelynd also wants the lighter-touch pieces from the earlier discussion: `acceptEdits` mode —
toggle with Shift+Tab — auto-approves file *edits*, which is currently ON as the interim measure.
The hook addresses the *bash* prompts that `acceptEdits` doesn't cover.)

---

## 6. Build plan (hand to Claude Code AFTER the design is reviewed)
Plan-first, no code until the decision logic + the §3.3 edge cases are confirmed with Katelynd.
1. Write the classifier script (bash or python3 — python3 likely easier for the clause-splitting
   and redirect regex). It reads stdin JSON, extracts `tool_input.command`, splits into clauses,
   classifies each, emits the `permissionDecision` JSON. Recommend python3 for maintainable regex.
2. Unit-test the classifier **directly** against the §1.1 corpus: all 7 Group-A commands →
   `allow`; the Group-B #8 command → `ask`. Add targeted cases for each §3.3 edge (a `> file`
   redirect → ask; `2>&1` → allow; `sed -i` → ask; `find -delete` → ask; `$( )` → ask;
   `git commit --amend` → ask).
3. Register the hook in `.claude/settings.json` + add the §5 deny rules. Run `/hooks` to confirm
   it's registered.
4. Live-validate: run a real diagnostic chain (should NOT prompt) and a real commit (SHOULD
   prompt). Confirm `acceptEdits` still governs edits.
5. Commit the hook script + settings.json as a reviewed repo artifact (durable, not chat-only).

### 6.1 Where it lives
Project-level `.claude/settings.json` + a script under `.claude/hooks/` (e.g.
`.claude/hooks/autoapprove_readonly_bash.py`), committed to the repo so it's durable and a fresh
session/Claude Code instance inherits it. (Matches the "nothing important lives only in chat"
discipline. Note: as of this writing `COLLABORATION_CONTEXT.md` itself is still untracked — same
durability point applies.)

---

## 7. Acceptance criteria
- All 7 Group-A corpus commands auto-approve (no prompt).
- The Group-B commit-bundle command prompts.
- Every §3.3 edge case behaves as specified (especially: `2>&1`/`2>/dev/null` allowed; real-file
  redirects, `sed -i`, `find -delete`, `git commit --amend`, command substitution → ask).
- The §5 deny rules block `rm`, `git push`, `git reset --hard`, `git clean`, `curl`, `wget`, and
  `.env`/secrets reads regardless of the hook.
- The classifier has direct unit tests; the corpus is encoded as fixtures.
- Hook + settings committed to the repo.

## 8. Open questions for Katelynd (resolve at build time)
1. **`pytest` / `python3 -c` auto-approve — confirm.** They run arbitrary code; recommended
   auto-approve for this repo (deny layer backstops), but it's a judgment call (§3.3). OK, or
   move to ask?
2. **Script language:** python3 (recommended, cleaner regex) or bash (no interpreter dependency)?
3. **Scope of deny list:** the §5 list is deliberately small. Add anything (e.g. `git rebase`,
   `chmod`, `pip install`) to hard-deny rather than just ask?
4. **Command substitution policy:** v1 recommends "force ask whenever `$( )`/backticks present"
   (simple + safe). OK, or invest in inspecting the inner command?
