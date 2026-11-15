#!/usr/bin/env bash
# Install cargo-nextest from its prebuilt release on github.com, pinned by sha256, into ~/.cargo/bin.
# Run: bash lib/tools/install-nextest.sh   (does nothing when that version is already installed)
#
# To move to a newer release, take the new version's x86_64-unknown-linux-gnu tarball hash from the release's
# .sha256 asset, check it against GitHub's own asset digest
# (https://api.github.com/repos/nextest-rs/nextest/releases), and change both lines below.
set -euo pipefail

VERSION=0.9.151
SHA256=1d4ce302b820c41f4b89c5fb9bce45f0f0c94882c1cf08fc360caf08be6e7df4
TARGET=x86_64-unknown-linux-gnu
BIN_DIR="${CARGO_HOME:-$HOME/.cargo}/bin"

if [ "$(uname -sm)" != "Linux x86_64" ]; then
    echo "install-nextest.sh: pinned for $TARGET only, not $(uname -sm)" >&2
    exit 1
fi
if [ -x "$BIN_DIR/cargo-nextest" ] && "$BIN_DIR/cargo-nextest" nextest --version 2>/dev/null | grep -q "cargo-nextest $VERSION "; then
    echo "cargo-nextest $VERSION already installed in $BIN_DIR"
    exit 0
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
url="https://github.com/nextest-rs/nextest/releases/download/cargo-nextest-$VERSION/cargo-nextest-$VERSION-$TARGET.tar.gz"
curl -sSfL --proto '=https' -o "$work/nextest.tar.gz" "$url"
echo "$SHA256  $work/nextest.tar.gz" | sha256sum --check --quiet
tar -xzf "$work/nextest.tar.gz" -C "$work" cargo-nextest
mkdir -p "$BIN_DIR"
install -m 0755 "$work/cargo-nextest" "$BIN_DIR/cargo-nextest"
"$BIN_DIR/cargo-nextest" nextest --version
