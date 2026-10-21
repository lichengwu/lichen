<div align="center">

# lichen

**A self-evolving skill framework for AI coding agents.**

[![CI](https://github.com/lichengwu/lichen/actions/workflows/ci.yml/badge.svg)](https://github.com/lichengwu/lichen/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/lichengwu/lichen?display_name=tag)](https://github.com/lichengwu/lichen/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
[![Star it](https://img.shields.io/github/stars/lichengwu/lichen?style=social)](https://github.com/lichengwu/lichen/stargazers)

`ai-agents` · `agent-skills` · `claude-code` · `codex` · `self-evolving` · `skill-library` · `hooks` · `python`

Clone it, use your agent as usual — the framework watches in the background, precipitates
reusable skills from what your agent actually does, and grows **your** skill system with a
human gate on anything risky. Export when ready; import anywhere. Fork it and it becomes yours.

[Install](#install) · [Quick start](#quick-start) · [How it works](#how-it-works) · [CLI](#cli) · [Make it yours](#make-it-yours)

</div>

---

## Why

Skill libraries rot. People collect `.md` files, forget what works, and lose track of what
their agents actually use. lichen treats skills as a **living, governed asset**:

- **Zero-effort capture** — session hooks passively collect usage signals. No dashboards,
  no daemons, no new workflow: keep using your agent exactly as before.
- **Automatic evolution** — repeatedly-edited skills get versioned (`generation++`,
  changelog, snapshots). Repeated intents with no skill coverage become candidate skeletons
  waiting to be forged.
- **Human gate on everything risky** — deterministic hygiene fixes run automatically (T0);
  trust changes, promotions, and deletions always ask you (T1).
- **Privacy first** — prompts are stored as hashes, never as text. Secret scanning gates
  every publish.
- **Boring by design** — Python stdlib only, no daemon, no database. `git clone` is the
  only dependency.

## Install

**One-line install** (downloads a verified release tarball):

```bash
curl -fsSL https://raw.githubusercontent.com/lichengwu/lichen/main/install.sh | sh
```

**Upgrade** an existing installation:

```bash
lichen upgrade
```

**From source** (the fork-and-own workflow — see [Make it yours](#make-it-yours)):

```bash
git clone https://github.com/lichengwu/lichen.git
cd lichen
python3 framework/bin/lichen init
```

Requirements: Python ≥ 3.9, `curl`. No pip packages, no node modules at runtime.

## Quick start

```bash
lichen init            # initialize local runtime state (idempotent)
lichen install-hooks   # register the passive signal hooks (writes settings.json, with backup)
lichen status          # what the system knows right now
```

Then just use your agent. lichen will:

| Signal | Automatic response |
|---|---|
| A local skill appears in a watched directory | Adopted into the hub after validation |
| A skill gets edited repeatedly | `generation++` + changelog + version snapshot |
| The same intent repeats 3+ times with no skill | A candidate skeleton is forged, surfaced in the digest |
| Missing sidecar / stale metadata / hygiene drift | Deterministic repair (T0) |
| Anything irreversible | A ≤3-line digest asks you (T1) |

## How it works

lichen hooks into agent session lifecycle events (`SessionStart`, `UserPromptSubmit`,
`PostToolUse`, `PreCompact`, `Stop`) and maintains a local signal ledger:

1. **Signals** — every request, skill load, file view, and edit is counted (never logged
   as text; prompts are hashed).
2. **Evolution pass** — a locked, rate-limited job (`lichen evolve --apply`, ≤10 auto
   actions/day) turns signals into: adoptions, version bumps, candidate skeletons, hygiene
   fixes.
3. **Governance** — every skill carries a three-axis sidecar: `kind` / `visibility`
   (public|private) / `execution` (auto|manual|hybrid), plus a 30-day probation for
   auto-created assets. Low-usage probationers get archived — by nomination, never silently.
4. **Hub** — your accumulated skills live in a separate hub repository (flat, standard
   Agent Skills format) that any agent can consume directly, and that can be published,
   shared, or synced without touching the framework.

Architecture decisions: [`.agents/adr/`](.agents/adr/) · Scope & non-goals: [`SCOPE.md`](SCOPE.md)

## CLI

One entry point, three command families:

```
lichen                  lifecycle & governance
lichen hub <sub>        your accumulated skill repository (SSOT)
lichen agents <sub>     distribute hub skills into each agent's directory
```

| Command | Purpose |
|---|---|
| `lichen init` | Initialize runtime state (idempotent) |
| `lichen status` | Human-readable system status |
| `lichen list` | Browse skills by category / bucket / origin |
| `lichen categorize` | Tag skills with scenario categories |
| `lichen evolve [--apply]` | Analyze signals; `--apply` executes T0 actions (dry-run by default) |
| `lichen adopt <path>` | Manually adopt a local skill |
| `lichen promote <id>` | Promote a forged candidate |
| `lichen run <id>` | Execute a manual skill (records usage signal) |
| `lichen trust <id> <confirm\|revoke>` | Human trust gate |
| `lichen evaluate / rollback / archive / unarchive` | Version & lifecycle maintenance |
| `lichen export / import` | skillpack/1 exchange (three-way merge, local evolution never clobbered) |
| `lichen install-hooks / uninstall-hooks` | Register/remove session hooks |
| `lichen update-check` | Check upstream drift for borrowed skills |
| `lichen doctor` | Self-check hooks, sidecars, and state files |
| `lichen version / upgrade` | Version info / self-update |
| `lichen hub init\|use\|status\|migrate\|publish\|import\|promote` | Hub repository operations |
| `lichen agents list\|sync\|doctor` | Materialize hub skills as per-skill symlinks into agent dirs |

## Make it yours

lichen is designed to be forked, not just installed:

```
fork upstream ──► use your agent daily ──► your hub grows ──► push it as YOUR repo
                     ▲                                                        │
                     └────────── merge upstream updates, keep evolving ◄──────┘
```

- The **upstream framework** never contains personal skills — only the engine plus a few
  seed skills. Your fork's history stays clean for merges.
- **Borrowed seeds** (`skills/borrowed/`) track upstream drift via `lichen update-check`.
- Exchange with others via content-addressed skill packs: `lichen export` / `lichen import`
  with three-way merge — their updates never overwrite your local evolution.

## Multi-agent distribution

One hub, many agents. `lichen agents sync` materializes per-skill symlinks into each
supported agent's skill directory (idempotent, conflict-safe):

| Agent | Status |
|---|---|
| Claude Code | supported (`~/.claude/skills`) |
| Codex | supported (`~/.agents/skills`) |
| pi | supported (`~/.agents/skills`, shared with Codex) |
| Qwen Code | supported (`~/.qwen/skills`) |
| WorkBuddy | adoption surface (creative layer) |
| Junie | planned |

Native readers of `~/.agents/skills` (Cursor, Copilot CLI, OpenCode, …) work with zero
extra configuration.

## Privacy

- Prompts and file paths are stored as **hashes**, not text.
- `visibility=private` skills are excluded from every publish path — structurally, not by
  convention.
- Publish gates run secret scanning; hard-pattern hits fail the build.
- Your signal ledger and hub live entirely on your machine.

## Project layout

```
framework/
  bin/lichen          CLI entry point
  lib/                engine (evolution, taxonomy, exchange, hub, agents, …)
  hooks/              session lifecycle hooks
  config.default.json configuration template (machine-local overrides in state/)
skills/
  starter/            demo skills: how to manage this framework
  borrowed/           upstream-tracked seed skills
scripts/              check / redact / publish gates
install.sh            installer (release tarball + checksum verify)
```

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The full test
suite runs in a disposable sandbox (your machine is never touched):
`sh scripts/test.sh`. Security concerns: [SECURITY.md](SECURITY.md). Release
process: [RELEASING.md](RELEASING.md).

## License

[MIT](LICENSE)
