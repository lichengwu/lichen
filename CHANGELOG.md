# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Test suite** (`scripts/test.sh` + `framework/tests/`): fully sandboxed
  harness — repo copy + fake `HOME`, so tests never touch the real machine.
  21 stdlib unit tests (taxonomy, meta, merge3, lock) plus a 9-step end-to-end
  pipeline (init → evolve adoption → fail-safe visibility → idempotency →
  agents sync → quarantine/promote → exchange roundtrip). CI runs it on
  Ubuntu and macOS.
- `CONTRIBUTING.md` now documents the testing workflow and sandbox semantics.

### Fixed

- Redaction phone-number pattern now uses digit-boundary lookarounds, so
  13-digit epoch millis (e.g. `"publishedAt": 1781935033901`) no longer
  false-hit; real 11-digit phone numbers still match. Redact unit tests added.
- `merge3.merge_text` dropped the trailing newline when merging text that
  ended with one, producing "no newline at end of file" diff noise in merged
  skills.
- **Empty config lists no longer erase built-in defaults.** A fresh install
  (empty `state/config.json`) plus the upstream template's empty
  `exclude_skills`/`ignore_skills` keys overrode the code defaults, so noise
  skills (xlsx/pptx) entered the adoption plan and excluded skills missed
  their private bucket. Empty lists in config layers are now treated as
  "not set", and the stale empty keys were removed from the template.
- `lichen init` next-step hint referenced the old `framework` command name.

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
