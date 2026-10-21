# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| latest release | ✅ |
| older releases | ❌ (upgrade via `lichen upgrade`) |

## Reporting a vulnerability

Do **not** open a public issue.

- Use GitHub's **Report a vulnerability** (Security → Advisories) on this repository, or
- email the maintainer via the contact address on their GitHub profile.

Include: affected version/commit, impact, and a minimal reproduction. You will get an
acknowledgment within 72 hours.

## Security model notes

lichen's threat model is intentionally simple and documented in
[`.agents/adr/`](.agents/adr/):

- **Skills are executable instructions for agents.** Importing untrusted content is a
  prompt-injection vector; that is why external content lands in a `quarantine/` bucket
  and requires an explicit `lichen hub promote` after review.
- **Publish paths are structurally excludes**, not conventions: `visibility=private`
  skills and the `private/` bucket are filtered out of every export/publish.
- **Secret scanning gates publishing.** Hard patterns (tokens, keys, known credential
  hashes) fail the build. The watchlist itself is never committed.
- **No network at runtime.** The engine is stdlib-only and makes no network calls;
  `lichen update-check` is the sole (read-only) exception.

If you find a way to bypass the publish guards or exfiltrate private content, that is a
high-priority report.
