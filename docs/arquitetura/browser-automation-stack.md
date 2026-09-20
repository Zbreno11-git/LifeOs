# Life OS — Browser Automation Stack
## Browser Harness + Jev + MCP + Chrome/CDP

**Status:** Experimental architecture validated through local fail tests  
**Date:** 2026-09-19  
**Purpose:** Persistent technical context / RAG seed for future agents, coding sessions and architecture decisions.

> **Nota histórica (2026-09-20):** este documento foi escrito antes do pivô Mac→Windows e da pausa da
> trilha de hardware de pulso (ver `docs/diario-de-bordo.md`, 2026-09-19, e
> `docs/arquitetura/viking-visao-e-arquitetura.md`). As referências a `mac-mcp`/macOS abaixo (seções
> de arquitetura e "Current Recommended Stack") são um registro histórico do momento em que foram
> validadas — não editadas — e não refletem a direção atual, que roda no Windows 11 mini PC ("Bosgame")
> e trata a automação de navegador (Jev + Browser Harness) como o mecanismo principal de execução,
> substituindo o controle local de PC.

---

# 1. Executive Summary

We validated a practical local browser automation stack for the Life OS project using:

- **Browser Harness** as the browser execution layer.
- **Chrome DevTools Protocol (CDP)** as the low-level browser control interface.
- **MCP** as the tool exposure protocol.
- **Gemini CLI** as an initial general-purpose planner/client.
- **Jev** as a specialized low-latency browser policy model.
- **OpenRouter** as the current Jev provider.
- A future **Life OS orchestrator** above all of these components.

The major architectural finding is:

> General-purpose LLMs are useful for planning, but they are inefficient when used for every browser micro-action. Jev-style policy models are substantially better suited to fast browser execution loops.

The second major finding is:

> Browser Harness is useful and fast, but the daemon/browser connection lifecycle must be supervised explicitly in any production-grade implementation.

The recommended production direction is therefore:

```text
User / Voice / Button / App
            │
            ▼
       Life OS Planner
   (Gemini / Claude / GPT)
            │
            ▼
     Browser Supervisor
            │
   ┌────────┴────────┐
   │                 │
health/recovery   browser goal
   │                 │
   ▼                 ▼
Browser Harness     Jev
   │                 │
   └────────┬────────┘
            ▼
      Fixed CDP endpoint
            │
            ▼
   Dedicated Chrome Profile
```

For a first product-grade MVP, keep Browser Harness. Do **not** rewrite the CDP runtime yet.

---

# 2. What Was Tested

## 2.1 Browser Harness CLI

Installed locally and connected to the user's real Chrome.

Initial smoke test:

```bash
browser-harness <<'PY'
print(page_info())
PY
```

Result:

- Read the active Chrome tab successfully.
- Returned URL, title and viewport information.
- No Browser Use cloud API key was required.

Second smoke test:

```bash
browser-harness <<'PY'
new_tab("https://example.com")
print(page_info())
PY
```

Result:

- Opened a new Chrome tab.
- Loaded `example.com`.
- Returned page metadata correctly.

Third smoke test:

```bash
browser-harness <<'PY'
print("ANTES:", page_info())
print("LINK:", js("document.querySelector('a').innerText"))
js("document.querySelector('a').click()")
wait_for_load()
print("DEPOIS:", page_info())
PY
```

Result:

- Read DOM.
- Executed an action.
- Navigated.
- Verified the resulting page.

Conclusion:

```text
READ       ✅
ACT        ✅
NAVIGATE   ✅
VERIFY     ✅
```

---

# 3. MCP Validation

Browser Harness already exposes an MCP server.

Server command used:

```bash
uvx --python 3.12 --from 'browser-harness[mcp]' browser-harness-mcp
```

Important behavior:

- When run directly, the process appears to "hang".
- This is expected.
- It is waiting for MCP messages through `stdin/stdout`.

## MCP Inspector

Started with:

```bash
npx @modelcontextprotocol/inspector \
  uvx --python 3.12 --from 'browser-harness[mcp]' browser-harness-mcp
```

Validated:

```text
MCP initialize          ✅
tools/list              ✅
resources/list          ✅
browser_page_info       ✅
browser_new_tab         ✅
MCP -> Chrome action    ✅
```

The Inspector proved that Browser Harness was operating as a real MCP server, not merely as a CLI wrapper.

Architecture validated:

```text
MCP Client
   │
   │ stdio
   ▼
browser-harness-mcp
   │
   ▼
Browser Harness
   │
   ▼
CDP
   │
   ▼
Chrome
```

---

# 4. Gemini as MCP Planner

Gemini CLI was installed and Browser Harness was registered as a user-level MCP server.

Conceptual configuration:

```text
Gemini CLI
    │
    ▼
browser-harness MCP
    │
    ▼
Chrome
```

The first language-level test asked Gemini to:

> Open a new tab at example.com and report the title.

Gemini autonomously selected multiple MCP tools:

```text
browser_new_tab
browser_wait_for_load
browser_page_info
```

The tab opened in the real Chrome and Gemini returned the correct result.

Validated:

```text
Natural language       ✅
LLM intent parsing     ✅
MCP tool selection     ✅
Multi-tool sequence    ✅
Chrome execution       ✅
Result observation     ✅
Final response         ✅
```

This proved the full agent loop:

```text
User
 ↓
Gemini
 ↓
MCP tool selection
 ↓
Browser Harness
 ↓
Chrome
 ↓
Observation
 ↓
Gemini
```

---

# 5. General LLM Browser Loop — Main Weakness

A more complex test asked Gemini to navigate GitHub through the site's own interface and locate:

```text
browser-use/browser-harness
```

The task eventually succeeded, but the execution was slow and tool-heavy.

Observed loop included:

```text
new_tab
wait_for_load
screenshot
ReadFile
press("/")
wait
screenshot
ReadFile
type(...)
press(Enter)
wait_for_load
screenshot
ReadFile
page_info
...
```

The run consumed many model calls and screenshots.

Gemini's session stats showed a large amount of token usage across routing, Flash and Pro models.

Key architectural conclusion:

> A general-purpose LLM is too expensive and slow if it has to reason between every single browser action.

The problem is not primarily Browser Harness latency.

The problem is:

```text
LLM reasoning
 ↓
tool call
 ↓
observation
 ↓
LLM reasoning
 ↓
tool call
 ↓
observation
 ↓
...
```

This is exactly the problem Jev/SUPERFAST is designed to reduce.

---

# 6. Jev Architecture

Jev is a specialized decision/policy model for browser action selection.

Instead of asking a general LLM to generate arbitrary actions, the system gives Jev:

```text
Available operations:
CLICK
TYPE_TEXT
SELECT
SCROLL
WAIT
DONE
BLOCKED

Available targets:
[1] button ...
[2] textbox ...
[3] combobox ...
```

Jev returns a bounded decision:

```text
operation = CLICK
target = 2
```

The model therefore operates over a constrained action space.

Conceptual difference:

```text
GENERAL LLM

state
 ↓
reasoning
 ↓
generated action
 ↓
tool call
 ↓
new state
 ↓
reasoning
 ↓
...


JEV

state
 ↓
choose operation + target
 ↓
execute
 ↓
state
 ↓
choose operation + target
 ↓
...
```

This is a better architecture for low-latency browser execution.

---

# 7. Jev via OpenRouter

Direct TypeSafe access was not used.

Instead, Jev was accessed through OpenRouter.

Working alias:

```text
~typesafe/jev-latest
```

OpenRouter resolved it to:

```text
typesafe/jev-1.13-20260917
```

Working endpoint:

```text
POST https://openrouter.ai/api/alpha/decisions
```

Minimal direct test:

```json
{
  "model": "~typesafe/jev-latest",
  "state": {
    "page": "Example page with a Search button"
  },
  "questions": {
    "operation": {
      "type": "choice",
      "instructions": "Choose the best next action.",
      "criteria": {
        "CLICK": "Click the Search button.",
        "WAIT": "Wait for the page."
      }
    }
  }
}
```

Response:

```text
HTTP 200
model: typesafe/jev-1.13-20260917
choice: CLICK
confidence: 0.55
input_tokens: 326
output_tokens: 31
cost: $0.000013692
provider: TypeSafe
```

Conclusion:

```text
OpenRouter key      ✅
Decisions endpoint  ✅
Jev model           ✅
Alias               ✅
Cost                extremely low
```

---

# 8. Fork / Patch of jev-ultrafast

Repository cloned:

```bash
git clone https://github.com/browser-use/jev-ultrafast.git
cd jev-ultrafast
uv sync
```

Environment:

```text
browser-harness 0.1.13
Python project runtime: 3.13.5
```

The original Jev provider call was modified from the TypeSafe endpoint to the OpenRouter Decisions endpoint.

Conceptual change:

```python
TypeSafe direct
    ↓
OpenRouter Decisions API
```

API key fallback was added:

```python
api_key = (
    os.environ.get("OPENROUTER_API_KEY")
    or os.environ["TYPESAFE_API_KEY"]
)
```

This preserved compatibility with the original test suite.

Validation:

```text
ruff               ✅
pytest             ✅
31 / 31 tests      ✅
```

A provider error message was also modified to surface the provider response body rather than only returning:

```text
HTTP 400
```

This was useful for debugging provider compatibility.

---

# 9. Jev Real Browser Test

The local Jev demo was started with:

```bash
uv run --env-file .env jev
```

Local demo:

```text
http://127.0.0.1:8766
```

A Google Flights browser task was run successfully.

Observed behavior:

- Fast step selection.
- Jev repeatedly selected browser actions.
- Final state reached `DONE`.
- Final decision latency shown in the UI was approximately hundreds of milliseconds.
- The run felt substantially faster than the equivalent general LLM browser loop.

Important caveat:

> The displayed latency for the final decision is not the total end-to-end task duration.

Still, the qualitative latency difference was obvious.

---

# 10. Critical Failure Found — Browser Harness Daemon

A subsequent GitHub test failed before Jev could operate.

Error:

```text
browser_harness.helpers._IPCResponseTimeout:
Runtime.evaluate timed out after 5s waiting for the daemon
```

Initial diagnosis:

```text
Jev                  not the failure
OpenRouter           not the failure
Python               not the failure

Browser Harness IPC / daemon connection lifecycle
                     = failure point
```

Browser Harness doctor:

```text
[ok]   chrome running
[ok]   daemon alive
[FAIL] active browser connections — 0
```

This is a critical finding.

The daemon process was alive, but it no longer had an active browser/CDP connection.

Therefore:

```python
process_alive == True
```

is **not enough** to consider the browser runtime healthy.

---

# 11. Recovery Test

Running:

```bash
browser-harness <<'PY'
print(page_info())
PY
```

successfully reattached to Chrome.

Immediately afterwards:

```bash
browser-harness --doctor
```

returned:

```text
[ok] chrome running
[ok] daemon alive
[ok] active browser connections — 1
```

Conclusion:

> Browser Harness can recover / reattach, but this lifecycle must be supervised explicitly.

Important state distinction:

```text
BEFORE

daemon process             alive
Chrome                     alive
daemon -> Chrome           disconnected


AFTER page_info()

daemon process             alive
Chrome                     alive
daemon -> Chrome           connected
```

---

# 12. Multi-Monitor Finding

The disconnected daemon was **not caused by a second monitor**.

CDP sees Chrome targets/tabs, not monitors as the primary abstraction.

A second monitor may influence which browser window or tab is considered focused, but it does not explain:

```text
active browser connections — 0
```

Important product rule:

> Never rely on "current active tab" as the task boundary.

A browser task should create and own its own target/tab.

---

# 13. New Recommended Browser Architecture

## Current experimental stack

```text
Planner / Agent
      │
      ▼
     Jev
      │
      ▼
Browser Harness Helpers
      │
      ▼
     IPC
      │
      ▼
    Daemon
      │
      ▼
     CDP
      │
      ▼
Personal Chrome
```

This works, but the lifecycle is fragile.

## Recommended Life OS v1 architecture

```text
                    LIFE OS
                       │
                       ▼
                  Planner LLM
             Gemini / Claude / GPT
                       │
                       ▼
               Browser Supervisor
                       │
             ┌─────────┴─────────┐
             │                   │
          health              task goal
             │                   │
             ▼                   ▼
 browser-harness doctor          Jev
             │                   │
             └─────────┬─────────┘
                       ▼
                Browser Harness
                       │
                       ▼
                 Fixed CDP URL
                       │
                       ▼
            Dedicated Chrome Profile
```

---

# 14. Browser Supervisor Requirements

The supervisor should verify:

```text
daemon_alive
AND
active_browser_connections > 0
AND
CDP probe succeeds
```

Not only:

```text
daemon_alive
```

Suggested lifecycle:

```python
def ensure_browser_ready():
    status = health_check()

    if status.connected and cdp_probe():
        return

    try_reattach()

    status = health_check()

    if status.connected and cdp_probe():
        return

    restart_daemon()

    status = health_check()

    if not status.connected:
        raise BrowserUnavailable()
```

Runtime policy:

```text
CDP timeout
   │
   ▼
health check
   │
   ├── connection alive
   │       └── retry operation once
   │
   └── disconnected
           └── reattach
                 │
                 └── retry once
                       │
                       └── restart daemon if still broken
```

Avoid infinite retries.

---

# 15. Dedicated Chrome Profile

For personal experimentation:

```text
normal Chrome
+ auto-discovery
```

is acceptable.

For unattended automation or productization, use a dedicated browser/profile.

Example:

```bash
mkdir -p ~/.life-os/chrome-profile

"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.life-os/chrome-profile"
```

Then:

```bash
export BU_CDP_URL=http://127.0.0.1:9222
```

Advantages:

- Fixed browser endpoint.
- Less dependence on browser discovery.
- No accidental navigation over personal active tabs.
- Better separation between user browsing and agent browsing.
- Easier supervision.
- Easier restart/recovery.
- More appropriate for unattended operation.

---

# 16. Tab Isolation Policy

A browser agent should never navigate over the user's active tab by default.

Required rule:

```text
New browser task
      │
      ▼
create new tab
      │
      ▼
capture targetId
      │
      ▼
all task actions use that targetId
      │
      ▼
verify completion
```

Never use:

```text
"whatever tab is currently active"
```

as a reliable task boundary.

This matters especially with:

- multiple Chrome windows;
- multiple monitors;
- personal tabs;
- Gmail;
- GitHub;
- ChatGPT;
- dashboards;
- authenticated applications.

---

# 17. Planner vs Executor Separation

This is now one of the central architectural decisions.

## Planner

Use a general reasoning model for:

- user intent;
- task decomposition;
- deciding which subsystem to use;
- choosing a website;
- deciding success criteria;
- interpreting ambiguous goals;
- deciding whether the task requires browser, macOS, APIs or hardware.

Examples:

```text
Gemini
Claude
GPT
Codex (for code generation / engineering tasks)
```

## Browser policy / executor

Use Jev for:

- clicking;
- typing;
- selecting;
- scrolling;
- waiting;
- choosing targets;
- short browser action loops.

Architecture:

```text
General LLM
    │
    │ "Find browser-use/browser-harness on GitHub"
    ▼
Browser Worker
    │
    ▼
Jev
    │
    ▼
Browser Harness
    │
    ▼
Chrome
```

The planner should not reason between every click unless recovery/escalation is required.

---

# 18. Life OS — Broader Architecture

Current direction:

```text
                         LIFE OS
                            │
                            ▼
                      ORCHESTRATOR
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
     macOS               Browser             Hardware
        │                   │                   │
     mac-mcp          Browser Worker        Arduino/ESP
        │                   │                   │
 AppKit / AX / CG       Jev + Harness         Serial
        │                   │                   │
        ▼                   ▼                   ▼
   native apps             Chrome             physical IO
```

Potential input sources:

```text
voice
keyboard shortcut
Arduino button
desktop UI
mobile UI
scheduled task
event hook
```

Potential outputs:

```text
macOS action
browser task
API action
hardware action
notification
workflow
```

---

# 19. Possible MVPs

## MVP A — Personal Life OS Browser Worker

Goal:

> Personal assistant controlling a dedicated Chrome profile.

Components:

```text
Planner
Browser Supervisor
Jev
Browser Harness
Dedicated Chrome
```

Capabilities:

- search web apps;
- operate dashboards;
- fill forms;
- retrieve information from authenticated web apps;
- execute repetitive browser workflows.

This is the most direct next MVP.

---

## MVP B — Unified Life OS MCP

Expose high-level tools:

```text
browser_goal(...)
open_project(...)
prepare_work_mode(...)
research_topic(...)
check_dashboard(...)
```

Internally:

```text
Life OS MCP
   ├── mac-mcp
   ├── browser worker
   ├── Arduino bridge
   └── APIs
```

Avoid exposing only low-level commands to the planner where possible.

Prefer:

```text
research_topic(...)
```

over a planner manually issuing:

```text
click
type
click
scroll
click
```

---

## MVP C — Hardware Triggered Workflows

Example:

```text
Breadboard button
       │
       ▼
Arduino event
       │
       ▼
Life OS
       │
       ├── open VS Code via mac-mcp
       ├── open browser task
       ├── load project dashboard
       └── start research mode
```

Arduino should emit simple events:

```text
BUTTON_1_PRESSED
```

The orchestrator decides the workflow.

---

## MVP D — Browser Worker Service

Run as a persistent local service:

```text
browser-worker
   │
   ├── health supervisor
   ├── task queue
   ├── tab isolation
   ├── Jev policy
   ├── Browser Harness
   └── structured task result
```

Possible interface:

```json
{
  "url": "https://github.com",
  "goal": "Find browser-use/browser-harness",
  "success_condition": "repository page open"
}
```

Response:

```json
{
  "status": "done",
  "url": "...",
  "title": "...",
  "duration_ms": 0,
  "steps": [],
  "verified": true
}
```

---

## MVP E — Productized Browser Automation

Later-stage product architecture:

```text
API / UI
   │
   ▼
Task Queue
   │
   ▼
Browser Worker
   │
   ├── dedicated browser/profile
   ├── health supervisor
   ├── Jev
   ├── Browser Harness
   └── verification
```

For multi-user SaaS, isolate browser environments per user/session.

Do not use one shared personal Chrome profile.

---

# 20. Possible Future Simplification — Remove the Daemon

Long-term possibility:

```text
TODAY

Jev
 ↓
Browser Harness helper
 ↓
IPC
 ↓
daemon
 ↓
CDP
 ↓
Chrome
```

Potential future architecture:

```text
Jev
 ↓
Custom Browser Runtime
 ↓
CDP WebSocket
 ↓
Chrome
```

Advantages:

- one fewer stateful layer;
- no Harness IPC daemon failure mode;
- full lifecycle control;
- easier instrumentation;
- deterministic connection ownership.

Disadvantages:

- we must reimplement browser primitives;
- more code;
- more maintenance;
- more CDP edge cases;
- less benefit from Browser Harness improvements.

Decision:

> Do not remove Browser Harness yet.

Only revisit this if repeated fail tests show that the daemon remains the dominant reliability bottleneck even with:

- fixed CDP endpoint;
- dedicated Chrome profile;
- health supervision;
- reattach/restart logic.

---

# 21. Fail Test Matrix

| Test | Result | Finding |
|---|---|---|
| Browser Harness reads active page | PASS | Local Chrome control works |
| Browser Harness opens new tab | PASS | Browser actions work |
| DOM/JS click + navigation | PASS | Read/act/verify loop works |
| Browser Harness MCP starts | PASS | Native MCP support works |
| MCP Inspector tool discovery | PASS | Tools exposed correctly |
| MCP page_info | PASS | MCP → Chrome works |
| MCP new_tab | PASS | MCP actions work |
| Gemini → MCP → Chrome | PASS | General LLM can autonomously select tools |
| Gemini multi-step GitHub task | PASS but slow | General LLM loop is inefficient |
| Jev direct OpenRouter call | PASS | Jev available now through OpenRouter |
| jev-ultrafast fork tests | PASS | 31/31 |
| Jev Google Flights run | PASS | Fast policy loop works |
| Jev GitHub run | FAIL | Browser Harness daemon had 0 active browser connections |
| `page_info()` reattach | PASS | Harness recovered connection |
| `doctor` after reattach | PASS | Connection returned to 1 |

---

# 22. Main Technical Findings

## Finding 1 — Browser Harness is a strong executor

Pros:

- local;
- fast primitives;
- real Chrome;
- MCP support;
- CDP-based;
- usable with existing authenticated browser sessions;
- low infrastructure overhead.

---

## Finding 2 — General-purpose LLM browser loops are wasteful

Observed behavior:

- repeated screenshots;
- repeated multimodal interpretation;
- long reasoning loops;
- repeated model calls;
- unnecessary uncertainty for trivial UI actions.

Use a planner only at the level where reasoning is useful.

---

## Finding 3 — Jev is a better browser policy layer

Jev offers:

- bounded action space;
- operation + target decision;
- very low API cost;
- low latency;
- no need for a general LLM at every action;
- compatibility with Browser Harness architecture.

---

## Finding 4 — Browser Harness daemon health is not binary

This is the critical reliability lesson:

```text
daemon alive != browser ready
```

Correct health state requires:

```text
daemon alive
+
active browser connection
+
successful CDP probe
```

---

## Finding 5 — Auto-discovery is fine for lab use, not ideal for unattended automation

Use:

```text
BU_CDP_URL
+
dedicated browser profile
```

for product-like execution.

---

## Finding 6 — Browser tasks need explicit ownership

Every task should own:

```text
browser instance/profile
or
target/tab
```

Do not depend on the user's currently focused browser tab.

---

# 23. Reliability Requirements Before Product

Minimum required before calling this product-ready:

1. Dedicated Chrome profile.
2. Fixed CDP endpoint.
3. Browser health supervisor.
4. Automatic reattach.
5. Controlled daemon restart.
6. Retry budget.
7. Per-task tab ownership.
8. Explicit success verification.
9. Task timeout.
10. Structured logs.
11. API/provider usage tracking.
12. Secret management.
13. Crash recovery.
14. Browser process cleanup.
15. Per-user isolation for SaaS.
16. Permission model for dangerous actions.
17. No arbitrary shell execution from browser policy.
18. Audit trail of browser actions.

---

# 24. Security Notes

Browser Harness controlling the user's real Chrome can potentially access:

- authenticated sessions;
- Gmail;
- GitHub;
- ChatGPT;
- dashboards;
- cookies/session state indirectly through browser actions;
- sensitive web applications.

Therefore:

```text
browser control = privileged capability
```

Recommended:

- dedicated automation profile;
- task isolation;
- user approval for dangerous actions;
- never log secrets;
- never commit `.env`;
- restrict arbitrary JS if productized;
- restrict filesystem access;
- separate planner permissions from executor permissions.

API keys must remain outside source control.

---

# 25. Recommended Next Fail Tests

## Test 1 — Dedicated Chrome + Fixed CDP

Run dedicated Chrome with:

```text
remote-debugging-port=9222
separate user-data-dir
```

Set:

```text
BU_CDP_URL=http://127.0.0.1:9222
```

Run repeated Jev tasks.

Target:

```text
20–30 sequential browser tasks
```

Measure:

- daemon disconnects;
- CDP failures;
- mean task duration;
- recovery events;
- Jev calls;
- cost;
- success rate.

---

## Test 2 — Browser Supervisor

Build minimal Python wrapper:

```text
health
reattach
restart
retry
```

Do not build a full product yet.

---

## Test 3 — Task Tab Isolation

Every task:

```text
create tab
capture target
operate only on target
verify
```

Test across:

- multiple browser windows;
- multiple monitors;
- many open tabs.

---

## Test 4 — Planner + Jev

Planner receives:

```text
"Find this repository"
```

Planner outputs:

```json
{
  "tool": "browser_goal",
  "url": "https://github.com",
  "goal": "..."
}
```

Then Jev takes over entirely.

Planner is called again only on:

```text
DONE
BLOCKED
FAILURE
ESCALATION
```

---

## Test 5 — macOS + Browser Unified Workflow

Example:

```text
"Start Altiva work mode"
```

Expected:

```text
mac-mcp
  → open VS Code

browser worker
  → open GitHub
  → open Supabase
  → open project dashboard

hardware
  → optional desk indicator
```

This is the first real Life OS workflow test.

---

# 26. Current Recommended Stack

```text
Planning:
    Gemini / Claude / GPT

Coding:
    Codex / Claude Code

Browser policy:
    Jev

Jev provider:
    OpenRouter Decisions API

Browser execution:
    Browser Harness 0.1.13

Transport:
    CDP

Browser:
    dedicated Chrome profile

Tool protocol:
    MCP

macOS automation:
    mac-mcp / native Swift MCP

Hardware:
    Arduino / ESP + serial/event bridge
```

---

# 27. Current Decision Log

## Decision: Keep Browser Harness

**Reason:** already validated, fast, local, MCP-compatible and avoids reimplementing CDP primitives.

Status:

```text
KEEP
```

---

## Decision: Add Browser Supervisor

**Reason:** daemon can be alive while browser connection count is zero.

Status:

```text
REQUIRED
```

---

## Decision: Use Dedicated Chrome for unattended tasks

**Reason:** auto-discovery / personal Chrome introduces lifecycle and context ambiguity.

Status:

```text
RECOMMENDED FOR MVP
```

---

## Decision: Use Jev as browser policy

**Reason:** lower latency and lower cost than general LLM loops.

Status:

```text
PROMISING / VALIDATED IN INITIAL TEST
```

---

## Decision: Keep general LLM above Jev

**Reason:** Jev is a browser action policy, not a general planner.

Status:

```text
KEEP
```

---

## Decision: Do not remove Browser Harness daemon yet

**Reason:** one observed failure is not enough to justify reimplementing browser runtime.

Status:

```text
DEFER
```

---

## Decision: High-level Life OS tools should exist

Prefer:

```text
browser_goal(...)
research_topic(...)
prepare_work_mode(...)
```

over giving a planner unrestricted low-level click/type control everywhere.

Status:

```text
DESIGN PRINCIPLE
```

---

# 28. Open Questions

1. How stable is Browser Harness with a dedicated Chrome profile and fixed CDP URL?
2. How often does the daemon lose browser connection under long-running workloads?
3. Does Jev generalize reliably across GitHub, dashboards, forms and dynamic SPAs?
4. How should browser task verification be implemented?
5. Should Jev operate through Browser Harness MCP, direct Python helpers, or a custom worker API?
6. How should planner ↔ browser worker contracts be structured?
7. When should the planner interrupt Jev?
8. What actions require human confirmation?
9. How should authentication be handled in a dedicated browser profile?
10. Is direct CDP worth implementing later?
11. How should browser tasks interact with mac-mcp workflows?
12. Can hardware-triggered workflows remain event-driven without adding HTTP locally?

---

# 29. Short Architecture Summary for Future Agents

If context is lost, start here:

```text
We are building Life OS.

Browser automation stack currently validated:

Planner LLM
    ↓
browser_goal(url, goal)
    ↓
Browser Supervisor
    ↓
Jev policy model via OpenRouter
    ↓
Browser Harness
    ↓
CDP
    ↓
Dedicated Chrome profile

Browser Harness already works locally and as MCP.

Jev was successfully accessed through:
https://openrouter.ai/api/alpha/decisions

Model alias:
~typesafe/jev-latest

The jev-ultrafast repo was patched to use OpenRouter.
Its full test suite passes: 31/31.

A real Jev Google Flights task succeeded and was fast.

Critical reliability finding:
Browser Harness daemon can remain alive while active browser connections == 0.

A simple page_info() call successfully reattached.

Production requirement:
health supervisor must check:
daemon alive + active browser connection + CDP probe.

Next major test:
dedicated Chrome profile + fixed BU_CDP_URL + 20–30 sequential Jev tasks.
```

---

# 30. Final Direction

The strongest architecture currently is:

```text
                     LIFE OS
                        │
                        ▼
                  General Planner
                        │
                        ▼
                  Browser Goal
                        │
                        ▼
                Browser Supervisor
                        │
               ┌────────┴────────┐
               │                 │
            health              Jev
               │                 │
               └────────┬────────┘
                        ▼
                Browser Harness
                        │
                        ▼
                       CDP
                        │
                        ▼
              Dedicated Chrome
```

General models decide **what** should happen.

Jev decides **which browser action** should happen next.

Browser Harness executes the action.

The Browser Supervisor guarantees that the underlying runtime is healthy.

This separation is currently the most promising foundation for the Life OS browser subsystem.
