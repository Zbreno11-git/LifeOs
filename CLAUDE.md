# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Life OS de Pulso: a wrist-worn assistant triggered by a button/gesture that captures thoughts, executes
commands, and answers by voice. This repo is early-stage — most of the architecture below is a *proposal*
being validated incrementally, not a built system. Treat claims about latency, battery life, or reliability
as unverified until a prototype measures them.

Full product/architecture reference: `Life OS de Pulso Visao e Arquitetura.docx` (v1.0, 19 setembro 2026).
That document's "Mac" execution path is superseded (see below) — the rest of its architecture still holds.
Running log of what's actually been done, in what order, and why: `docs/diario-de-bordo.md` — **read this
first** to know current status, then update it (new dated entry) whenever you make non-trivial progress.
Don't assume this CLAUDE.md file auto-syncs with that log; re-check it each session.

**Do not suggest `mac-control-mcp` again.** It was the reference doc's original choice for local-machine
control, but its `Package.swift` fixes `platforms: [.macOS(.v14)]` — a hard build *and* runtime requirement
— and the available Mac is a 2017 Intel Ventura 13 machine with no Sonoma upgrade path. That path is dead;
the project now targets a Windows 11 mini PC ("Bosgame") instead. See `docs/diario-de-bordo.md`, 2026-09-19
entry, for the full reasoning.

## Repo layout

- `src/lifeos/` — Python package for the Life OS backend/tooling (currently a stub).
- `tests/` — pytest suite for `src/lifeos`.
- `docs/` — `diario-de-bordo.md` (progress log, keep updated) and other project docs.
- `data/` — local data, gitignored except `.gitkeep`.
- `windows-mcp/` — gitignored clone of the fork used for local Windows control (see Architecture). Not part
  of this repo's own history; it's its own git checkout with `origin`/`upstream` remotes.
- `LifeOS Arduino Fail Test/` — the current, working milestone (Roadmap "Fase 1"): an Arduino Uno R3 button
  wired to D2/GND sends `BUTTON` over Serial; a Python script on the Windows box (Bosgame) reads it and
  calls the local Windows-MCP server's `PowerShell` tool to toggle system mute. No HTTP, Wi-Fi, cloud, or
  LLM involved at this stage — see its own `README.md` for the exact wiring/setup steps.
  - `arduino/button_serial/button_serial.ino` — debounced button sketch, prints `BUTTON` at 115200 baud.
  - `pc/serial_mcp_bridge.py` — asyncio bridge: reads the Serial port, calls the MCP `PowerShell` tool via
    stdio (spawns `uv run windows-mcp serve` from the cloned fork; path overridable via `WINDOWS_MCP_DIR`).
    Run with `--simulate` to test the MCP call without an Arduino attached. This script itself is plain
    Python + pyserial, so it can be edited/lint-checked from any OS — it only *runs* correctly on Windows.

## Commands

```bash
source .venv/bin/activate
pip install -e ".[dev]"        # editable install + pytest/ruff
pip install -r requirements.txt  # current-phase runtime deps (mcp, pyserial)

pytest                         # run tests (testpaths = tests/)
pytest tests/test_smoke.py::test_version   # single test
ruff check .                   # lint (line-length 100, src+tests)
```

For the fail-test bridge specifically (must actually run on the Windows box — see its README):
```powershell
cd "LifeOS Arduino Fail Test"
python pc\serial_mcp_bridge.py --simulate
python pc\serial_mcp_bridge.py --port COM5   # real port varies
```

`requirements.txt` tracks only the dependencies needed for the *current* roadmap phase — add to it (and to
`docs/diario-de-bordo.md`) incrementally as later phases are built, rather than front-loading future deps
(e.g. FastAPI/uvicorn arrive with MVP 0.5, not before).

## Architecture (target, per the reference doc)

Proposed end-to-end flow: button/gesture → capture on ESP32 (XIAO ESP32-S3) → HTTPS → Life OS API (FastAPI)
→ STT → intent routing → execution → structured response → TTS when useful → playback on the wristband.
Known/simple commands can skip the LLM in the router.

Three execution destinations, each with a distinct owner:
- **Cloud** (Life OS API): notes, reminders, persisted user data.
- **Windows PC / Bosgame** (via the *Life OS Windows Agent*, a component that still needs to be built):
  local actions on the PC. (The reference doc calls this the "Mac Agent" acting on "the Mac" — read those
  terms as this Windows PC now; see the note above.)
- **Firmware** (on-device): volume/state changes local to the wristband itself.

**Windows Agent design** — the key architectural decision to preserve (adapted from the doc's Mac Agent):
- [`Windows-MCP`](https://github.com/CursorTouch/Windows-MCP) (external, Python, MIT license, 7k+ stars,
  runs on Windows 7 through 11, stdio/SSE/streamable-HTTP transports, no computer-vision dependency — uses
  the UI Automation tree) runs **on the Windows PC**. Fork for this project:
  https://github.com/Zbreno11-git/Windows-MCP.
- The Life OS Windows Agent starts it as a **local MCP client over stdio** (`uv run windows-mcp serve`) —
  MCP is only used for this local hop, never between the wristband/cloud and the PC.
- The Windows Agent keeps an **outbound**, authenticated connection to the backend (WebSocket is the initial
  choice, unvalidated) — it never opens an inbound/public port on the PC.
- The backend must never forward an arbitrary, model-generated tool name to the Windows Agent. It emits a
  typed, allow-listed intent; the Agent is what translates that into a local MCP tool call sequence (e.g.
  `PowerShell` with a specific, known command — not an arbitrary one).
- A fork of `Windows-MCP` is only warranted to modify it if there's a *proven need*. Forking it to build
  from source / pin a version (current practice) is not that.

Minimal command envelope (backend → Windows Agent): `request_id, device_id, target, action, parameters,
issued_at, expires_at, confirmation_required`. Response: `request_id, status, result|error, completed_at`.
`request_id` dedupes retries; `expires_at` stops a stale command firing after the PC reconnects.

Security/ops constraints called out in the doc (apply these when building the Agent/API):
- Authenticate wristband, user, and PC separately; pair the PC to the account before accepting remote
  commands. TLS + short-lived/rotatable credentials; never embed AI-service keys in firmware.
- MVP keeps the remote action allow-list small. Screen reads, clipboard, sending messages, executing code,
  and irreversible ops need their own rules and explicit confirmation before being enabled. `Windows-MCP`'s
  `PowerShell`/`Registry`/`FileSystem` tools are broad by design — the Windows Agent, not the raw MCP server,
  is what should enforce the allow-list.
- Treat transcripts and on-screen UI content as untrusted data — text seen on screen must never itself grant
  the agent new permissions.
- Distinguish *received*, *executed*, and *confirmed*: an HTTP 200 from the API is not completion; only the
  Windows Agent's own result confirms it. Surface "pending" rather than false success.
- If the PC is asleep/locked/disconnected/missing permissions, return a clear unavailability signal rather
  than hanging or silently failing.

## Roadmap (source of truth: docs/diario-de-bordo.md, keep both in sync)

1. **Fase 1 — Fail test** (current): Arduino → Serial → Python (on the Bosgame) → local MCP command. Exit
   criterion: button fires once; success/error observable. Does *not* validate Wi-Fi, MCP-over-network, or
   voice.
2. **MVP 0.5 — Canal remoto**: ESP32 → authenticated API → Windows Agent → local MCP → play/pause. Exit
   criterion: end-to-end result, reconnection, and duplicate-command handling tested; status LED reflects
   real result.
3. **MVP 1 — Áudio de entrada**: XIAO + INMP441 → Wi-Fi upload → STT → note/action.
4. **MVP 2 — Resposta e ergonomia**: add ToF sensor, MAX98357A speaker output, buttons, TTS.
5. **Produto**: case, pairing, updates, observability, action catalog.

Open questions the doc leaves unresolved (don't silently assume answers): off-network connectivity for the
wristband; which commands need explicit confirmation vs. run directly; Windows Agent provisioning/update and
permission recovery (no TCC-equivalent audit done yet); measurable targets for latency/battery/STT
accuracy/cost; whether notes/reminders or PC control should be the first user-facing priority.
