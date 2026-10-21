# Releasing

How to cut a lichen release. The process is intentionally boring.

## Versioning

Semantic versioning. The version lives in `package.json` (single source of truth;
`lichen version` reads it) and in the `CHANGELOG.md` entry.

## Steps

1. **Finalize the changelog.** Add/merge a `CHANGELOG.md` entry under the new version.
   Notes should follow the existing categories: *Added / Changed / Fixed / Security*.

2. **Run the gates.**

   ```bash
   bash scripts/check.sh
   bash scripts/redact.sh
   python3 -m py_compile framework/bin/lichen framework/lib/*.py
   ```

3. **Bump `package.json`** to the release version and commit:

   ```bash
   git commit -m "chore(release): v0.X.Y"
   ```

4. **Tag and push.**

   ```bash
   git tag -a vX.Y.Z -m "lichen vX.Y.Z"
   git push origin main --follow-tags
   ```

   The `release` workflow fires on `v*` tags: it builds the tarball with
   `git archive`, generates the SHA-256 checksum, creates a GitHub Release with
   auto-generated notes, and attaches `lichen-X.Y.Z.tar.gz` +
   `lichen-X.Y.Z.tar.gz.sha256`.

5. **Refine the release notes.** Edit the release on GitHub: keep the auto-generated
   *What's Changed* section, add a short **Highlights** paragraph at the top (2-4
   bullets, user-facing language), and confirm the checksum line renders.

6. **Verify the install path** on a clean machine or temp home:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/lichengwu/lichen/main/install.sh | sh
   lichen version
   ```

## Release notes conventions

- First section: **Highlights** — what a user would care about, no internal jargon.
- Then the auto-generated PR list (categorized via `.github/release.yml`).
- Breaking changes go first, in bold, with a migration one-liner.
- Every release ships the tarball + checksum; binaries are intentionally not
  provided (stdlib-only Python; the tarball *is* the artifact).
