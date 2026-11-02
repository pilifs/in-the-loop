#!/usr/bin/env bash
# Installs TLC, the TLA+ model checker, as tla2tools.jar in ~/tools (or $TLA_TOOLS_DIR), where `jvmcontract tlc`
# looks for it. No sudo. Rerun with TLC_UPGRADE=1 to fetch the latest release again.
#
#   bash install-tlc.sh
set -euo pipefail

dir=${TLA_TOOLS_DIR:-$HOME/tools}
jar=$dir/tla2tools.jar
url=${TLA_TOOLS_URL:-https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar}

command -v java >/dev/null || { echo "install-tlc.sh: java is needed to run TLC (install a JDK first)" >&2; exit 1; }
command -v curl >/dev/null || { echo "install-tlc.sh: curl is needed to download tla2tools.jar" >&2; exit 1; }

if [ -f "$jar" ] && [ -z "${TLC_UPGRADE:-}" ]; then
  echo "TLC already installed: $jar (TLC_UPGRADE=1 refetches it)"
else
  mkdir -p "$dir"
  echo "Downloading tla2tools.jar from $url"
  curl -fsSL -o "$jar.part" "$url"
  mv "$jar.part" "$jar"
fi

version=$(java -cp "$jar" tlc2.TLC -h 2>&1 | grep -o 'Version [0-9][^ ]*' | head -1 || true)
echo "TLC ${version:-installed} at $jar"
if [ "$dir" != "$HOME/tools" ] && [ -z "${TLA2TOOLS_JAR:-}" ]; then
  echo "jvmcontract looks in ~/tools: export TLA2TOOLS_JAR=$jar"
fi
