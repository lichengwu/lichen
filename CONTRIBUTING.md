# Contributing & Development Guide

Thanks for your interest in developing lichen! This document explains how the
repository is organized, how to set up, where to make changes, and the rules a
contribution must pass. For release mechanics see [RELEASING.md](RELEASING.md);
for security reports see [SECURITY.md](SECURITY.md).

## What lichen is (one paragraph)

lichen is a **self-evolving skill framework for AI coding agents**. Session hooks
passively record usage signals (hashes only, never prompt text); an evolution pass
turns those signals into governed changes — adopting local skills, versioning edited
ones, forging candidate skeletons for repeated intents, and repairing metadata
drift. Deterministic and reversible fixes run automatically (T0); anything
trust-affecting or destructive asks a human (T1). Skills accumulate in a separate
**hub** repository and are distributed to agents as per-skill symlinks. The engine
is Python ≥ 3.9, **stdlib only**, no daemon.

## Repository tour

```
framework/
  bin/lichen          CLI entry (argparse; every subcommand is a small cmd_* function)
  lib/                engine — see module map below
  hooks/              session lifecycle hooks (installed into agent settings.json)
  config.default.json config template; machine-local overrides live in state/config.json (gitignored)
  templates/          SKILL.md scaffold used by forging/promotion
skills/
  starter/lichen-ops  demo skill: how to operate this framework
  borrowed/           upstream-tracked seed skills (drift checked via `lichen update-check`)
scripts/              gates: check.sh (structure) · redact.sh (secret scan) · test.sh (unit + sandbox E2E) · publish.sh (human-gated commit/push)
install.sh            installer: release tarball + SHA-256 → ~/.lichen + ~/.local/bin/lichen
.agents/adr/          architecture decision records — read 0002 first
```

### Engine module map (`framework/lib/`)

| Module | Responsibility |
|---|---|
| `paths.py` | Path & config resolution (`LICHEN_HOME`, defaults + machine-local overlay) |
| `signals.py` | Append-only signal ledger (`state/signals.jsonl`) |
| `analyze.py` | Signal → evolution decisions (pure functions, no I/O) |
| `evolve.py` | Evolution pass: adoption, versioning, candidates, hygiene (T0/T1, lock + daily budget) |
| `lifecycle.py` | Probation, trust gate, maturity, archival |
| `meta.py` | Three-axis sidecars (kind / visibility / execution), index, version snapshots |
| `validate.py` | Skill validation — BLOCK stops automation, WARN is advisory |
| `scan.py` | Local skill discovery (skips symlink entries by design) |
| `taxonomy.py` | Controlled-vocabulary scenario classification (keyword scoring) |
| `exchange.py` | skillpack/1 export/import; `merge3.py` provides the three-way line merge |
| `hub.py` | Hub repository operations (init/use/status/migrate/publish/import/promote) |
| `hubloc.py` | Hub location resolution — `local:` today; git/webdav/sftp schemes reserved |
| `agents.py` | Agent registry + per-skill symlink materialization + doctor |
| `redact.py` | Secret scanning (hard patterns fail; soft patterns substitute) |
| `lock.py` | `fcntl` file lock for all evolution write paths |
| `digest.py` | Human-readable status summaries (≤3-line session digest) |
| `evaluate.py` | Generation-over-generation metric comparison |
| `install_hooks.py` | Hook registration into agent settings (with backup) |
| `util.py` | Shared helpers (frontmatter parsing, hashing, tree copy, …) |

## Setup

```bash
git clone https://github.com/lichengwu/lichen.git
cd lichen
python3 framework/bin/lichen init      # local runtime state (gitignored)
python3 framework/bin/lichen doctor    # should be OK on a fresh clone
```

Requirements: Python ≥ 3.9. There are **no runtime dependencies** and no build step.

## Ground rules

1. **No runtime dependencies.** The engine must run on a bare Python 3.9+ install.
   Dev-time tools (node, gitleaks) are fine but must never be imported by the engine.
2. **No daemon.** Everything runs in-process or via hooks; nothing listens on a socket.
3. **Privacy is structural.** Prompts are hashed, never persisted as text. A change
   that stores user content verbatim will be rejected.
4. **T0/T1 discipline.** Automatic actions must be deterministic and reversible, and
   respect the daily budget. Trust, promotion, deletion, and anything irreversible
   are T1 (human-gated). When in doubt, make it T1.
5. **No personal skills upstream.** `skills/` only ever contains `starter/` demos and
   `borrowed/` upstream-tracked seeds. Personal skills belong in your fork's hub,
   never in a PR here.

## Development workflow

1. Branch from `main` (feature branches; no force-push to `main`).
2. Make your change. Keep one logical change per PR.
3. Run the local gates:

   ```bash
   bash scripts/check.sh                                                # structure
   bash scripts/redact.sh                                               # secret scan
   python3 -m py_compile framework/bin/lichen framework/lib/*.py framework/hooks/*.py
   sh scripts/test.sh                                                   # full suite (sandboxed)
   ./framework/bin/lichen doctor                                        # smoke
   ```

4. If you changed anything under `skills/`, add a `CHANGELOG.md` entry (CI enforces
   this on PRs). Engine-only changes are welcome to include one but not required.
5. Open a PR using the template. CI runs the same gates plus the changelog check.
6. Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
   `chore:`, `refactor:`).

## Where to make changes

### Engine (`framework/lib/`, `framework/bin/lichen`)

- Keep modules single-purpose and stdlib-only; pure functions over I/O where
  possible (`analyze.py` is the model to follow).
- New CLI subcommands: add a `cmd_*` function, register it in `build_parser()`,
  and add a row to the CLI table in `README.md`.
- Any new **automatic write path** must: acquire `lock.file_lock`, respect the
  daily budget, and classify as T0 (reversible) or T1 (gate). If it writes user
  content, it must pass `validate.py` first.
- Config additions go in `config.default.json` with a safe default; document the
  machine-local override path in a comment.

### Hooks (`framework/hooks/`)

- Hooks must exit 0 in all but catastrophic cases and stay fast (< 1 s); they run
  inside the user's agent session. Never raise into the agent's output.

### Skills (`skills/`)

- Format: standard Agent Skills frontmatter (`name`, `description`) plus lichen's
  `.skill-meta.json` sidecar — see `skills/starter/lichen-ops/` for a complete
  example. `description` must be written as a trigger phrase ("Use when …").
- `starter/` = framework demos; `borrowed/` = externally authored skills kept for
  reference (record the upstream source and license in `skills/borrowed/CREDITS.md`,
  and keep the sidecar's drift-tracking fields intact).
- Skill changes require a `CHANGELOG.md` entry (CI enforces this).
- Validation is local: `bash scripts/check.sh` and `lichen doctor`.

### Scripts & gates (`scripts/`)

- `redact.sh` hard patterns are release-safety-critical: additions welcome,
  removals need strong justification.
- `publish.sh` is a human-gated path by design; don't add automation around it.

## Testing

Run everything with:

```bash
sh scripts/test.sh
```

The harness is **fully sandboxed** — it copies the repository to a temp dir,
points `HOME` at a fake home, and runs the whole pipeline there. Your real
`~/Skills`, `~/.agents/*`, and framework `state/` are never touched. Set
`LICHEN_TEST_KEEP=1` to keep the sandbox for debugging (the path is printed
on failure).

Two layers:

1. **Unit tests** (`framework/tests/`, stdlib `unittest`): pure-function
   coverage for `taxonomy`, `meta`, `merge3`, `lock`. Run them directly with
   `python3 -m unittest discover -s framework/tests -t framework`.
2. **End-to-end** (in `scripts/test.sh`): init → evolve adoption →
   fail-safe visibility check → idempotency → agents sync/doctor →
   quarantine → promote → materialization → export/import roundtrip.

CI runs the full suite on Ubuntu and macOS. When you add a nontrivial pure
function, add a unit test next to the existing ones rather than a `__main__`
self-check.

## PR checklist

- [ ] `bash scripts/check.sh` passes
- [ ] `bash scripts/redact.sh` passes (no secret-scan hits)
- [ ] `python3 -m py_compile framework/bin/lichen framework/lib/*.py framework/hooks/*.py` passes
- [ ] `sh scripts/test.sh` passes (unit + sandbox E2E)
- [ ] If `skills/` changed: `CHANGELOG.md` entry included
- [ ] No runtime dependencies added (stdlib-only rule)
- [ ] No personal/private skills introduced upstream
- [ ] T0/T1 classification considered for any new automation
- [ ] README CLI table updated if commands changed

## Issues

- Bugs: use the bug template; include `lichen doctor` output (redact private paths).
- Features: use the feature template — describe the **signal** (what observed agent
  behavior motivates this), not just the mechanism, and state the proposed T0/T1
  classification.

## Releasing

Maintainers only — see [RELEASING.md](RELEASING.md). In short: bump
`package.json`, finalize `CHANGELOG.md`, tag `vX.Y.Z`, push the tag; the release
workflow builds the tarball, checksum, and GitHub Release automatically.
