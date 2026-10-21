# Summary

<!-- One or two sentences: what does this PR do and why? -->

## Changes

<!-- Bullet list of the substantive changes -->

## Checklist

- [ ] `bash scripts/check.sh` passes
- [ ] `bash scripts/redact.sh` passes (no secret-scan hits)
- [ ] `python3 -m py_compile framework/bin/lichen framework/lib/*.py` passes
- [ ] If `skills/` changed: a changeset is included (`npx changeset`)
- [ ] No runtime dependencies added (stdlib-only rule)
- [ ] No personal/private skills introduced upstream
- [ ] T0/T1 classification considered for any new automation
