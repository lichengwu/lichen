#!/bin/sh
# lichen installer — standard install & upgrade path.
#
# Install (latest release):
#   curl -fsSL https://raw.githubusercontent.com/lichengwu/lichen/main/install.sh | sh
#
# Install a specific version:
#   curl -fsSL .../install.sh | sh -s -- v0.6.0
#
# Upgrade an existing installation:
#   lichen upgrade        (equivalent to re-running this script)
#
# Layout:
#   $LICHEN_INSTALL_DIR (default ~/.lichen)   — framework files
#   $LICHEN_BIN_DIR     (default ~/.local/bin) — `lichen` symlink
#
# The framework itself is stdlib-only Python; nothing else is downloaded.
set -eu

REPO="lichengwu/lichen"
INSTALL_DIR="${LICHEN_INSTALL_DIR:-$HOME/.lichen}"
BIN_DIR="${LICHEN_BIN_DIR:-$HOME/.local/bin}"
VERSION="${1:-}"

say() { printf 'lichen installer: %s\n' "$1"; }
die() { printf 'lichen installer: ERROR: %s\n' "$1" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is required (https://curl.se)"
command -v python3 >/dev/null 2>&1 || die "python3 (>= 3.9) is required"

# ---- resolve version ----
if [ -z "$VERSION" ]; then
  say "resolving the latest release ..."
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" |
    sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')
  [ -n "$VERSION" ] || die "could not resolve the latest release (network?)"
fi
case "$VERSION" in
  v*) VNUM="${VERSION#v}" ;;
  *)  VNUM="$VERSION"; VERSION="v$VERSION" ;;
esac
say "installing lichen $VERSION"

# ---- download & verify ----
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
BASE="https://github.com/$REPO/releases/download/$VERSION"
say "downloading $BASE/lichen-$VNUM.tar.gz"
curl -fsSL "$BASE/lichen-$VNUM.tar.gz" -o "$TMP/pkg.tar.gz" ||
  die "download failed (release $VERSION not found?)"
curl -fsSL "$BASE/lichen-$VNUM.tar.gz.sha256" -o "$TMP/pkg.tar.gz.sha256" ||
  die "checksum download failed"

if command -v sha256sum >/dev/null 2>&1; then
  SHA_TOOL="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  SHA_TOOL="shasum -a 256"
else
  say "WARNING: no sha256 tool found, skipping verification"
  SHA_TOOL=""
fi
if [ -n "$SHA_TOOL" ]; then
  expected=$(cut -d' ' -f1 "$TMP/pkg.tar.gz.sha256" | tr -d '[:space:]')
  actual=$($SHA_TOOL "$TMP/pkg.tar.gz" | cut -d' ' -f1 | tr -d '[:space:]')
  [ -n "$expected" ] || die "empty checksum file"
  [ "$expected" = "$actual" ] || die "checksum mismatch (expected $expected, got $actual)"
fi

# ---- install ----
mkdir -p "$INSTALL_DIR"
tar -xzf "$TMP/pkg.tar.gz" -C "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/framework/bin/lichen"

mkdir -p "$BIN_DIR"
ln -sfn "$INSTALL_DIR/framework/bin/lichen" "$BIN_DIR/lichen"

# ---- verify ----
GOT=$("$BIN_DIR/lichen" version 2>/dev/null || true)
[ "$GOT" = "lichen $VNUM" ] || die "post-install check failed (got '$GOT')"

say "installed $GOT"
say "  files:  $INSTALL_DIR"
say "  binary: $BIN_DIR/lichen -> $INSTALL_DIR/framework/bin/lichen"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "NOTE: $BIN_DIR is not on your PATH. Add to your shell profile:"
     say "      export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
say "next: run 'lichen init' inside your project, then 'lichen install-hooks'"
