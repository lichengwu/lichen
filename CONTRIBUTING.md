# Contributing to lichen

Thanks for your interest in contributing! lichen is a framework for self-evolving
agent skill systems — small, boring, and reliable on purpose.

## Development setup

```bash
git clone https://github.com/lichengwu/lichen.git
cd lichen
python3 framework/bin/lichen init
python3 framework/bin/lichen doctor
```

Requirements: Python ≥ 3.9 (stdlib only — do not add runtime dependencies).

## Ground rules

1. **No runtime dependencies.** The engine must run on a bare Python 3.9+ install.
2. **No daemon.** Everything runs in-process or via hooks; nothing listens.
3. **Privacy is structural.** Prompts are hashed, never logged as text. Any change
   that persists user content verbatim will be rejected.
4. **T0/T1 discipline.** Deterministic, reversible hygiene fixes may run
   automatically (T0). Anything destructive, trust-affecting, or irreversible
   requires a human gate (T1). When in doubt, make it T1.
5. **No personal skills upstream.** `skills/` only ever contains `starter/` demos
   and `borrowed/` upstream-tracked seeds.

## Pull requests

- One logical change per PR; keep the diff reviewable.
- Run the local gates before pushing:

  ```bash
  bash scripts/check.sh     # structure check
  bash scripts/redact.sh    # secret scan (hard patterns fail the build)
  python3 -m py_compile framework/bin/lichen framework/lib/*.py
  ```

- If your PR changes anything under `skills/`, add a changeset
  (`npx changeset`) describing the skill-level change.
- CI must pass (structure check + secret scan + changeset presence).

## Reporting issues

- Bug reports: use the bug template and include the output of `lichen doctor`
  (redact any paths you consider private).
- Feature proposals: use the feature template; explain the *signal* (what agent
  behavior would drive it), not just the mechanism.

## Security

See [SECURITY.md](SECURITY.md). Please do not open public issues for vulnerabilities.
