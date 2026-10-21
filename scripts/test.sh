#!/bin/sh
# lichen sandbox test harness.
#
# Runs unit tests and a full end-to-end pipeline inside a disposable sandbox:
#   - the repository is copied to a temp dir (all state/skills writes land there)
#   - HOME is pointed at a fake home (all ~ paths — hub, scan_dirs, agent
#     targets, hooks settings — resolve inside the sandbox)
#   - the local machine is never touched; the sandbox is deleted on success
#
# Usage: scripts/test.sh          (set LICHEN_TEST_KEEP=1 to keep the sandbox)

set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/lichen-test.XXXXXX")

cleanup() {
    status=$?
    if [ "$status" -eq 0 ] && [ "${LICHEN_TEST_KEEP:-0}" != "1" ]; then
        rm -rf "$SANDBOX"
    else
        echo "==> sandbox kept for debugging: $SANDBOX"
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM

say() { echo "==> $*"; }
die() { echo "FAIL: $*" >&2; exit 1; }

BIN="$SANDBOX/repo/framework/bin/lichen"

# ---------------------------------------------------------------------------
say "building sandbox: $SANDBOX"
mkdir -p "$SANDBOX/home/.workbuddy/skills" "$SANDBOX/home/.agents/skills"
rsync -a \
    --exclude '.git' \
    --exclude 'framework/state' \
    --exclude 'dist' \
    --exclude 'skills/.private' \
    --exclude 'skills/local' \
    "$REPO/" "$SANDBOX/repo/"

# Everything below runs against the sandbox: fake HOME, repo copy.
HOME="$SANDBOX/home"
export HOME

# ---------------------------------------------------------------------------
say "[1/9] unit tests (stdlib unittest)"
(cd "$SANDBOX/repo/framework" && python3 -m unittest discover -s tests -t . -q)

# ---------------------------------------------------------------------------
say "[2/9] seeding fixture skills into sandbox scan dir"
make_skill() {
    dir="$1"; sid="$2"; blurb="$3"
    mkdir -p "$dir"
    cat > "$dir/SKILL.md" <<EOF
---
name: $sid
description: Use when $blurb. 当需要 $blurb 时使用。
---

# $sid

Trigger this skill when $blurb.
EOF
}
make_skill "$HOME/.workbuddy/skills/wb-alpha" "wb-alpha" "testing sandbox adoption"
make_skill "$HOME/.workbuddy/skills/wb-beta"  "wb-beta"  "testing idempotent adoption"

# ---------------------------------------------------------------------------
say "[3/9] init + hub init"
"$BIN" version
"$BIN" init >/dev/null
"$BIN" hub init >/dev/null
test -d "$HOME/Skills" || die "hub root not created under sandbox HOME"

# ---------------------------------------------------------------------------
say "[4/9] evolve --apply adopts both fixtures into the hub"
"$BIN" evolve --apply >/dev/null
test -d "$HOME/Skills/wb-alpha" || die "wb-alpha not adopted into hub"
test -d "$HOME/Skills/wb-beta"  || die "wb-beta not adopted into hub"

# fail-safe visibility: adopted skills must be private
for sid in wb-alpha wb-beta; do
    vis=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('visibility'))" \
        "$HOME/Skills/$sid/.skill-meta.json")
    [ "$vis" = "private" ] || die "$sid visibility is '$vis', expected private (fail-safe)"
done

# ---------------------------------------------------------------------------
say "[5/9] evolve is idempotent (no re-adoption, no growth)"
before=$(ls "$HOME/Skills" | wc -l | tr -d ' ')
"$BIN" evolve --apply >/dev/null
after=$(ls "$HOME/Skills" | wc -l | tr -d ' ')
[ "$before" = "$after" ] || die "hub grew from $before to $after on second evolve"

# ---------------------------------------------------------------------------
say "[6/9] agents sync materializes per-skill symlinks"
"$BIN" agents sync >/dev/null
for sid in wb-alpha wb-beta; do
    link="$HOME/.agents/skills/$sid"
    [ -L "$link" ] || die "missing symlink for $sid"
    case "$(readlink "$link")" in
        *Skills*) : ;;
        *) die "symlink for $sid does not point into the sandbox hub: $(readlink "$link")" ;;
    esac
done
"$BIN" agents doctor >/dev/null || die "agents doctor reported problems"

# ---------------------------------------------------------------------------
say "[7/9] external skill lands in quarantine, not in agents"
EXT="$SANDBOX/ext-skill"
make_skill "$EXT" "ext-skill" "testing external quarantine flow"
"$BIN" hub import "$EXT" >/dev/null
test -d "$HOME/Skills/quarantine/ext-skill" || die "external skill not quarantined"
"$BIN" agents sync >/dev/null
[ -e "$HOME/.agents/skills/ext-skill" ] && die "quarantined skill was materialized"

say "promote quarantined skill -> public zone -> materialized"
"$BIN" hub promote ext-skill >/dev/null
test -d "$HOME/Skills/ext-skill" || die "promoted skill missing from hub root"
"$BIN" agents sync >/dev/null
[ -L "$HOME/.agents/skills/ext-skill" ] || die "promoted skill not materialized"

# ---------------------------------------------------------------------------
say "[8/9] exchange roundtrip: export a pack and re-import it (same source)"
"$BIN" export --name sandbox-pack --out "$SANDBOX/dist" >/dev/null
PACK=$(ls "$SANDBOX"/dist/*.zip 2>/dev/null | head -1)
[ -n "$PACK" ] || die "export produced no zip in $SANDBOX/dist"
"$BIN" import "$PACK" >/dev/null || die "re-importing our own export failed"

# ---------------------------------------------------------------------------
say "[9/9] final doctor sweep"
"$BIN" doctor >/dev/null || die "framework doctor reported problems"

say "ALL TESTS PASSED"
