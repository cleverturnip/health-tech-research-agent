"""Phase 3 (GATE-1) — in-app candidate discovery.

Step 1 (this): the grounding + prompt builders — pure, offline, no OpenAI. Builds the ledger-grounded context
(thesis + full scored roster + manual overrides + exclude list) and fills the locked discovery system prompt
(spec §2a). The OpenAI web-search call + the chat/curate/approve UI come in later steps.

Rule 7: this only assembles CONTEXT for the LLM to PROPOSE candidates; the human approves at GATE-1 and the
deterministic §B scoring happens downstream (research).
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from .. import dashboard, dashboard_html, ledger

DEFAULT_MODEL = "gpt-5.4-mini"  # matches the research pipeline (research_runner.DEFAULT_MODEL)

# The locked discovery system prompt (spec §2a — signed off 2026-07-04). Only {thesis} / {researched} /
# {overrides} / {roster} are filled; the rest is fixed wording (highest-stakes change — do not edit without sign-off).
PROMPT_TEMPLATE = """You are helping Katelynd find health-tech companies to research for her career search — she wants a ROLE at a company that fits her, not an investment. Propose real, current companies to add to her research list.

Her target market (her saved thesis — the baseline; she may refine it in the chat):
{thesis}

Already researched — do NOT propose any of these again:
{researched}

Her manual priority overrides — where she personally disagreed with the model and set her own priority, in her own words. This is the strongest signal of her taste:
{overrides}
Lean toward companies that resemble the ones she raised; treat the ones she lowered as a weaker fit.

Her full scored roster (how everything she's researched ranks, and why — the numbers-led view):
{roster}

Propose 6-10 candidates that:
- are real, currently-operating health-tech companies — USE WEB SEARCH to verify each exists and get its latest status (stage, recent funding). Never invent or guess; if you can't verify it, drop it.
- fit her thesis (plus anything she adds in the chat) and resemble her raised overrides where it makes sense.
- are NOT already in her researched list.

For each: company name; one line on why it fits (tie to her thesis or her overrides); a quick search signal (stage + latest funding, or what they do).

Then ask if she wants to refine (more like one, earlier-stage, different segment, drop some). Keep it a conversation; approval is a separate step. Be honest about assumptions and about any company you're unsure fits - don't pad the list."""


def _roster_line(record: dict) -> str:
    s = record["scores"]
    return (f'{record["company"]} · {record["segment_label"]} · {record["model"]} · {record["stage"]} · '
            f'{record["final_priority"]} · Bg {record["bg_display"]}/PMF {s["pmf"]}/Strain {s["strain"]}/'
            f'FINAL {record["final_display"]} · {record["key_flag"]}')


def grounding_payload(entries: list[dict], thesis: str, *, taxonomy_dir: Any = None) -> dict:
    """Build the four grounding strings from the ledger: thesis, exclude list, overrides (with reasons), and the
    full compact scored roster. Raw research write-ups are deliberately NOT included (spec §2)."""
    records = dashboard.build_company_records(entries, require_reviewed=False, taxonomy_dir=taxonomy_dir)
    by_company = {r["company"].lower(): r for r in records}

    researched = ", ".join(sorted(r["company"] for r in records)) or "(none yet)"
    roster = "\n".join(_roster_line(r) for r in records) or "(no companies scored yet)"

    override_lines = []
    for entry in entries:
        decision = entry.get("decision") or {}
        if decision.get("human_override"):
            r = by_company.get(str(entry.get("company", "")).lower(), {})
            context = f'{r.get("segment_label", "")} · {r.get("model", "")} · {r.get("stage", "")}'
            override_lines.append(
                f'{entry.get("company")} ({context}): model said {entry.get("model_priority")}, '
                f'she set {ledger.final_priority(entry)} — \'{decision.get("override_reason") or ""}\'')
    overrides = "\n".join(override_lines) if override_lines else "(no manual overrides yet)"

    return {"thesis": (thesis or "").strip() or "(no thesis saved yet)",
            "researched": researched, "overrides": overrides, "roster": roster}


def build_system_prompt(entries: list[dict], thesis: str, *, taxonomy_dir: Any = None) -> str:
    """The full discovery system prompt (locked wording) with the ledger grounding filled in."""
    return PROMPT_TEMPLATE.format(**grounding_payload(entries, thesis, taxonomy_dir=taxonomy_dir))


# ---------------------------------------------------------------------------
# The discovery call (Step 2) — client-injected (offline tests pass a fake), OpenAI responses API + web search
# ---------------------------------------------------------------------------

# A MECHANICAL output-format addendum (NOT part of the locked §2a reasoning wording — it only structures the
# output so the app can render the proposed companies as a selectable list; it does not change which companies
# the model proposes).
_FORMAT_SUFFIX = """

---
OUTPUT FORMAT: write your conversational reply for Katelynd first. THEN, only if you proposed companies in this message, append a fenced code block labelled `candidates` holding a JSON array of exactly those companies — each {"company": "...", "why": "...", "signal": "..."}. Proposed none => omit the block entirely. Put nothing after the block. Example:
```candidates
[{"company":"Acme Health","why":"metabolic coaching with daily app engagement","signal":"Series A, $14M (2024)"}]
```"""

_CANDIDATES_RE = re.compile(r"```candidates\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_candidates(text: str) -> tuple[str, list[dict]]:
    """Split model output into (display_text, candidates). Extracts the fenced ```candidates JSON block; a
    missing or malformed block yields no candidates and never raises."""
    text = text or ""
    match = _CANDIDATES_RE.search(text)
    if not match:
        return text.strip(), []
    display = (text[:match.start()] + text[match.end():]).strip()
    try:
        data = json.loads(match.group(1).strip())
        candidates = [{"company": str(c.get("company", "")).strip(),
                       "why": str(c.get("why", "")).strip(),
                       "signal": str(c.get("signal", "")).strip()}
                      for c in data if isinstance(c, dict) and str(c.get("company", "")).strip()]
    except (ValueError, TypeError, AttributeError):
        candidates = []
    return display, candidates


# The prompt ASKS the model not to re-propose researched companies, but it doesn't reliably obey (the live-verify
# saw it re-propose "Levels"/"Culina Health"). Rule 7: enforce the exclude list DETERMINISTICALLY here, so a dupe
# can never reach the tray regardless of the model. Matching is name-normalized, tolerant of a trailing generic
# word ("Levels" ↔ "levels health") — deliberately a touch aggressive: better to drop a name-colliding proposal
# than to re-surface something already researched.
_GENERIC_SUFFIX = {"health", "inc", "llc", "co", "corp", "labs", "ai", "app"}


def _name_keys(name: Any) -> set[str]:
    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(name).lower())).strip()
    keys = {normalized} if normalized else set()
    tokens = normalized.split()
    if len(tokens) > 1 and tokens[-1] in _GENERIC_SUFFIX:
        keys.add(" ".join(tokens[:-1]))
    return keys


def drop_researched(candidates: list[dict], entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Split proposed candidates into (kept, dropped_names), dropping any whose name matches a company already in
    the ledger — the deterministic guard behind the prompt's do-not-repeat instruction."""
    researched: set[str] = set()
    for entry in entries:
        researched |= _name_keys(entry.get("company", ""))
    kept, dropped = [], []
    for candidate in candidates:
        if _name_keys(candidate.get("company", "")) & researched:
            dropped.append(str(candidate.get("company", "")).strip())
        else:
            kept.append(candidate)
    return kept, dropped


def discover(client: Any, system_prompt: str, conversation: list[dict], *, model: str = DEFAULT_MODEL,
             max_output_tokens: int = 1500, use_web_search: bool = True) -> dict:
    """One discovery turn. `conversation` is the running list of {"role": "user"|"assistant", "content": str}.
    Returns `{"reply": <display text>, "candidates": [{company, why, signal}, ...]}`. The OpenAI `client` is
    injected (offline tests pass a fake), mirroring the research pipeline."""
    kwargs: dict = {"model": model, "instructions": system_prompt + _FORMAT_SUFFIX,
                    "input": list(conversation), "max_output_tokens": max_output_tokens}
    if use_web_search:
        kwargs["tools"] = [{"type": "web_search"}]
        kwargs["tool_choice"] = "auto"
    response = client.responses.create(**kwargs)
    reply, candidates = parse_candidates(getattr(response, "output_text", "") or "")
    return {"reply": reply, "candidates": candidates}


# ---------------------------------------------------------------------------
# The /discover UI (Step 3) — thesis editor + grounded chat + candidate tray + approve.
# The chat is client-managed (the browser keeps the running conversation and posts it back each turn); the
# server rebuilds the grounded system prompt fresh every turn, so edits to the thesis/ledger take effect live.
# ---------------------------------------------------------------------------

_DISCOVER_CSS = """
.dsctop{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.dsccol{display:grid;grid-template-columns:1fr 340px;gap:18px;align-items:start}
@media(max-width:900px){.dsccol{grid-template-columns:1fr}}
.card{background:var(--surface-2);border:1px solid var(--border);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
.card+.card{margin-top:16px}
.card .dh{font-size:13px;font-weight:700;color:var(--navy);margin-bottom:4px}
.card .dsub{font-size:12px;color:var(--text-secondary);margin-bottom:12px}
.thesisbox{font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:9px;width:100%;min-height:120px;resize:vertical;box-sizing:border-box;line-height:1.55}
.chatlog{border:1px solid var(--border);border-radius:11px;background:var(--surface-1);padding:14px;height:46vh;min-height:300px;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
.msg{max-width:82%;font-size:13px;line-height:1.55;padding:9px 13px;border-radius:13px;white-space:normal;word-wrap:break-word}
.msg.user{align-self:flex-end;background:var(--navy);color:#fff;border-bottom-right-radius:4px}
.msg.assistant{align-self:flex-start;background:var(--surface-2);border:1px solid var(--border);color:var(--text-primary);border-bottom-left-radius:4px}
.msg .err{color:#791F1F;font-weight:600}
.chatrow{display:flex;gap:8px;margin-top:12px}
.chatrow textarea{flex:1;font:inherit;font-size:13px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:9px;resize:none;min-height:44px;max-height:140px;box-sizing:border-box;line-height:1.5}
.tray{display:flex;flex-direction:column;gap:9px;max-height:52vh;overflow-y:auto}
.traempty{font-size:12px;color:var(--text-secondary);line-height:1.5}
.cand{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--border);border-radius:11px;padding:10px 12px;background:var(--surface-1);cursor:pointer;position:relative}
.cand input{margin-top:2px}
.cand .cn{font-size:13px;font-weight:700;color:var(--navy)}
.cand .cw{font-size:12px;color:var(--text-primary);margin-top:2px;line-height:1.45}
.cand .cs{font-size:11.5px;color:var(--text-secondary);margin-top:3px}
.candx{position:absolute;top:6px;right:8px;border:none;background:none;font-size:16px;line-height:1;color:var(--text-muted);cursor:pointer}
.candx:hover{color:#791F1F}
#approvemsg{font-size:12.5px;color:#1E7A3E;font-weight:600;margin-top:10px;line-height:1.5}
.btnp{font:inherit;font-size:13px;font-weight:600;border-radius:9px;padding:9px 15px;cursor:pointer;border:1px solid var(--navy);background:var(--navy);color:#fff}
.btnp[disabled]{opacity:.45;cursor:not-allowed}
.btns{font:inherit;font-size:13px;font-weight:600;border-radius:9px;padding:9px 15px;cursor:pointer;border:1px solid var(--border-strong);background:var(--surface-2);color:var(--navy)}
"""

# Static (NON-f-string) client logic — keeps the running conversation, renders replies, accumulates the proposed
# candidates into the tray (dedup by name, deselect/remove before approving), and posts the approved set.
_DISCOVER_JS = r"""
(function(){
  var conversation=[], candidates={};
  var chat=document.getElementById('chat'), input=document.getElementById('msg'), sendBtn=document.getElementById('send');
  var tray=document.getElementById('tray'), approveBtn=document.getElementById('approve'), approvemsg=document.getElementById('approvemsg');
  function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':s);return d.innerHTML;}
  function addMsg(role,text){var el=document.createElement('div');el.className='msg '+role;el.innerHTML=esc(text).replace(/\n/g,'<br>');chat.appendChild(el);chat.scrollTop=chat.scrollHeight;return el;}
  function renderTray(){
    var keys=Object.keys(candidates);approveBtn.disabled=keys.length===0;
    if(!keys.length){tray.innerHTML='<div class="traempty">No candidates yet — describe your target market and the assistant will propose real companies here. You can drop any before approving.</div>';return;}
    tray.innerHTML='';
    keys.forEach(function(k){var c=candidates[k];var row=document.createElement('label');row.className='cand';
      row.innerHTML='<input type="checkbox" checked data-k="'+esc(k)+'"><div><div class="cn">'+esc(c.company)+'</div><div class="cw">'+esc(c.why)+'</div><div class="cs">'+esc(c.signal)+'</div></div><button type="button" class="candx" data-k="'+esc(k)+'" title="Remove">&times;</button>';
      tray.appendChild(row);});
    tray.querySelectorAll('.candx').forEach(function(b){b.addEventListener('click',function(ev){ev.preventDefault();delete candidates[b.getAttribute('data-k')];renderTray();});});
  }
  function addCandidates(list){(list||[]).forEach(function(c){if(c&&c.company){candidates[c.company.toLowerCase()]=c;}});renderTray();}
  function send(){
    var text=input.value.trim();if(!text)return;
    addMsg('user',text);conversation.push({role:'user',content:text});input.value='';
    input.disabled=true;sendBtn.disabled=true;var thinking=addMsg('assistant','…');
    fetch('/discover/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation:conversation})})
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(d){thinking.innerHTML=esc(d.reply).replace(/\n/g,'<br>');conversation.push({role:'assistant',content:d.reply});addCandidates(d.candidates);})
      .catch(function(){thinking.innerHTML='<span class="err">Could not reach the assistant. Check the app has an OpenAI key, then try again.</span>';})
      .then(function(){input.disabled=false;sendBtn.disabled=false;input.focus();});
  }
  sendBtn.addEventListener('click',send);
  input.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
  approveBtn.addEventListener('click',function(){
    var chosen=[];tray.querySelectorAll('input[type=checkbox]').forEach(function(cb){if(cb.checked){chosen.push(candidates[cb.getAttribute('data-k')]);}});
    if(!chosen.length){alert('Select at least one candidate to approve.');return;}
    if(!confirm('Approve '+chosen.length+' candidate(s)? This saves the research candidate list to your Drive.'))return;
    approveBtn.disabled=true;
    fetch('/discover/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidates:chosen})})
      .then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(d){approvemsg.innerHTML='Saved <b>'+esc(d.count)+'</b> candidate(s) to <b>'+esc(d.filename)+'</b> in your Drive. Research runs on the approved list next.';})
      .catch(function(){approveBtn.disabled=false;alert('Could not save the candidate list — does the app have edit access to your Drive folder?');});
  });
  renderTray();
})();
"""


def render_page(thesis: str, *, roster_count: int) -> str:
    """The GATE-1 discovery page: a saveable thesis, the grounded chat, and the candidate tray + approve."""
    thesis_val = html.escape(thesis or "")
    grounded = (f'grounded on your saved thesis and all {roster_count} scored companies'
                if roster_count else 'grounded on your saved thesis')
    crumb = ('<div class="dsctop"><div class="apptitle" style="color:var(--navy)">GATE-1 Discovery</div>'
             '<div><a class="btns" style="text-decoration:none" href="/">&larr; Dashboard</a></div></div>')
    thesis_card = (
        '<form method="post" action="/discover/thesis" class="card">'
        '<div class="dh">Your target market (thesis)</div>'
        '<div class="dsub">The baseline the assistant reads every turn — who you are and what you\'re looking for. '
        'Refine it any time; saving updates the grounding.</div>'
        f'<textarea class="thesisbox" name="thesis" placeholder="Describe the kind of company and role you\'re looking for…">{thesis_val}</textarea>'
        '<div style="margin-top:10px"><button type="submit" class="btns">Save thesis</button></div></form>')
    chat_card = (
        '<div class="card"><div class="dh">Discover candidates</div>'
        f'<div class="dsub">Chat with the assistant ({grounded}). It proposes real, web-verified companies '
        'you haven\'t researched yet; they collect in the tray to the right. Approving is a separate step.</div>'
        '<div id="chat" class="chatlog"><div class="msg assistant">Tell me about the kind of health-tech company '
        'you want to research next — the space, stage, or anything specific. I\'ll suggest real companies that fit '
        'your thesis and aren\'t already on your list.</div></div>'
        '<div class="chatrow"><textarea id="msg" rows="1" placeholder="Describe your target market… (Enter to send)"></textarea>'
        '<button type="button" id="send" class="btnp">Send</button></div></div>')
    tray_card = (
        '<div class="card"><div class="dh">Candidate list</div>'
        '<div class="dsub">Proposed companies collect here. Uncheck or remove any, then approve.</div>'
        '<div id="tray" class="tray"></div>'
        '<div style="margin-top:14px"><button type="button" id="approve" class="btnp" disabled>'
        'Approve candidate list &rarr;</button><div id="approvemsg"></div></div></div>')
    body = crumb + thesis_card + f'<div class="dsccol">{chat_card}{tray_card}</div>'
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>GATE-1 Discovery</title>'
        f'<style>{dashboard_html._CSS}{_DISCOVER_CSS}</style></head><body><div class="wrap">{body}</div>'
        f'<script>{_DISCOVER_JS}</script></body></html>')
