# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-10-21

First public release of the framework skeleton.

### Added

- **Hub repository layer** (`lichen hub`): a dedicated git repository as the single
  source of truth for accumulated skills — flat standard Agent Skills layout, a
  `private/` bucket that is structurally excluded from every publish path, and a
  `quarantine/` bucket for unreviewed external content (`import` → `promote`).
- **Multi-agent distribution** (`lichen agents`): materialize hub skills as per-skill
  symlinks into each supported agent directory (Claude Code, Codex, pi, Qwen Code);
  WorkBuddy as an adoption surface; idempotent sync with conflict-safe doctor checks.
- **Hub location resolution** with a remote-mode extension point (git/webdav/sftp
  schemes reserved; local mode only in this release).
- **Adoption safety**: default `visibility=private` on adopt (fail-safe), symlink
  entries skipped during scanning, hub skills merged into the in-memory index to
  prevent double-adoption.
- **Scenario taxonomy** (`lichen categorize`): controlled vocabulary + deterministic
  keyword scoring, multi-label per skill, `--auto` / `--backfill`.
- **Concurrency safety**: file lock around all evolution write paths; daily auto-action
  budget (default 10).
- **Lifecycle governance**: three-state usage counting (load/view/patch), 30-day
  probation with capacity-competition archival, `lichen trust` human gate,
  `lichen evaluate` between generations.
- **skillpack/1 exchange protocol**: content-addressed export/import with three-way
  merge; local evolution is never clobbered by imports.
- **Installer**: `install.sh` (release tarball + SHA-256 verification) and
  `lichen upgrade` self-update.

### Changed

- CLI entry point renamed `framework/bin/framework` → `framework/bin/lichen`.
- Hook environment variable renamed `SKILL_FORGE_HOME` → `LICHEN_HOME`.
- The upstream repository ships **no personal skills** — only the engine and seed
  skills (`starter/`, `borrowed/`).

### Security

- Publish gates: git-tracking guard for local secret stores, credential watchlist
  history guard, secret scanning with hard-pattern failure.
- Local secret storage (`redact.rules`, `id-watchlist.txt`) is never committed;
  only `.template` versions are tracked.

## [0.5.x] - 2026-10-19 → 2026-10-20

Internal development releases: core signal hooks, signal ledger, evolution pass,
validate-before-land pipeline, version snapshots and rollback, redaction pipeline.

[0.6.0]: https://github.com/lichengwu/lichen/releases/tag/v0.6.0
