#!/usr/bin/env bash
# Installs the /verify-bytecode and /add-tla-model skills for Claude Code, jvmcontract, the verifier they run, and
# TLC, the model checker the second one runs.
#
#   curl -fsSL https://terminalvalue.net/verify-bytecode-skill/install.sh | bash
#
# What it does: copies the skills into ~/.claude/skills/<name> (so `/verify-bytecode` and `/add-tla-model` exist in
# every project), builds and installs `jvmcontract` with cargo if it is not on the PATH (installing Rust first if
# there is no cargo), downloads tla2tools.jar into ~/tools if there is no TLC, and checks for the tools the skills
# use (a JDK, JBMC, gh, Maven or Gradle), printing how to get the missing ones. It never needs sudo. Rerun it to
# update the skills.
#
# Settings, as environment variables:
#   VERIFY_BYTECODE_REPO     the git repository (default https://github.com/pilifs/in-the-loop)
#   VERIFY_BYTECODE_REF      the branch or tag (default main; empty for the repository's default branch)
#   VERIFY_BYTECODE_SKILLS   which skills to install (default "verify-bytecode add-tla-model")
#   CLAUDE_SKILLS_DIR        where skills go (default ~/.claude/skills)
#   JVMCONTRACT_UPGRADE=1    rebuild jvmcontract even if it is installed
#   NO_RUST=1                never install Rust; skip jvmcontract if cargo is missing
#   NO_TLC=1                 never download TLC
set -euo pipefail

REPO=${VERIFY_BYTECODE_REPO:-https://github.com/pilifs/in-the-loop}
REF=${VERIFY_BYTECODE_REF-main}
branch=()
[ -n "$REF" ] && branch=(--branch "$REF")
SKILLS_DIR=${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}
SKILLS=${VERIFY_BYTECODE_SKILLS:-verify-bytecode add-tla-model}
SKILLS_PATH=plugins/jvmcontract/skills

say() { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok() { printf '    \033[32m✓\033[0m %s\n' "$*"; }
miss() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null || die "git is needed to fetch the skill (https://git-scm.com/downloads)"

# 1. The skills.
say "Fetching the skills from $REPO${REF:+ ($REF)}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if ! git clone --quiet --depth 1 --filter=blob:none --sparse "${branch[@]}" "$REPO" "$tmp/repo" 2>/dev/null; then
  git clone --quiet --depth 1 "${branch[@]}" "$REPO" "$tmp/repo"
fi
git -C "$tmp/repo" sparse-checkout set "$SKILLS_PATH" 2>/dev/null || true
commit=$(git -C "$tmp/repo" rev-parse --short HEAD)

mkdir -p "$SKILLS_DIR"
for skill in $SKILLS; do
  [ -f "$tmp/repo/$SKILLS_PATH/$skill/SKILL.md" ] || die "$SKILLS_PATH/$skill/SKILL.md is not in $REPO${REF:+ at $REF}"
  rm -rf "$SKILLS_DIR/$skill"
  cp -R "$tmp/repo/$SKILLS_PATH/$skill" "$SKILLS_DIR/$skill"
  chmod +x "$SKILLS_DIR/$skill/scripts/"*.sh "$SKILLS_DIR/$skill/templates/"*.sh 2>/dev/null || true
  printf 'repo: %s\nref: %s\ncommit: %s\ninstalled: %s\n' "$REPO" "$REF" "$commit" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$SKILLS_DIR/$skill/INSTALLED"
  ok "/$skill installed in $SKILLS_DIR/$skill (commit $commit)"
done

# 2. jvmcontract, the verifier.
say "Checking jvmcontract"
cargo_env="$HOME/.cargo/env"
[ -f "$cargo_env" ] && . "$cargo_env"
if command -v jvmcontract >/dev/null && [ -z "${JVMCONTRACT_UPGRADE:-}" ]; then
  ok "$(jvmcontract --version) at $(command -v jvmcontract) (JVMCONTRACT_UPGRADE=1 rebuilds it)"
else
  if ! command -v cargo >/dev/null; then
    if [ -n "${NO_RUST:-}" ]; then
      miss "cargo is missing and NO_RUST is set: jvmcontract was not installed. Install Rust (https://rustup.rs), then: cargo install --git $REPO${REF:+ --branch $REF} --locked jvmcontract"
    else
      say "Installing Rust with rustup (minimal profile, in ~/.cargo and ~/.rustup), to build jvmcontract"
      curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path
      . "$cargo_env"
    fi
  fi
  if command -v cargo >/dev/null; then
    say "Building jvmcontract from $REPO${REF:+ ($REF)}; this compiles a Rust crate and takes a few minutes the first time"
    cargo install --quiet --git "$REPO" "${branch[@]}" --locked jvmcontract
    ok "$(jvmcontract --version 2>/dev/null || "$HOME/.cargo/bin/jvmcontract" --version) installed in $HOME/.cargo/bin"
    case ":$PATH:" in
      *":$HOME/.cargo/bin:"*) ;;
      *) miss "$HOME/.cargo/bin is not on your PATH; add it to your shell profile: export PATH=\"\$HOME/.cargo/bin:\$PATH\"" ;;
    esac
  fi
fi

# 3. TLC, the model checker /add-tla-model runs.
case " $SKILLS " in
  *" add-tla-model "*)
    say "Checking TLC"
    tlc_jar=${TLA2TOOLS_JAR:-$HOME/tools/tla2tools.jar}
    if [ -f "$tlc_jar" ]; then ok "TLC at $tlc_jar"
    elif command -v tlc >/dev/null; then ok "tlc on the PATH"
    elif [ -n "${NO_TLC:-}" ]; then miss "no TLC and NO_TLC is set: /add-tla-model can write a model but not check it. Later: bash $SKILLS_DIR/add-tla-model/scripts/install-tlc.sh"
    elif ! command -v java >/dev/null; then miss "no TLC, and no java to run it: install a JDK, then bash $SKILLS_DIR/add-tla-model/scripts/install-tlc.sh"
    else bash "$SKILLS_DIR/add-tla-model/scripts/install-tlc.sh" | sed 's/^/    /'
    fi ;;
esac

# 4. The tools the skills run.
say "Checking the tools the skills use"
if command -v javac >/dev/null; then ok "JDK: $(javac -version 2>&1)"; else miss "no JDK (javac): needed to compile the pull request. Install Temurin from https://adoptium.net or with SDKMAN (https://sdkman.io)"; fi
if command -v jbmc >/dev/null; then ok "JBMC: $(jbmc --version 2>&1 | head -1)"; else
  hint="build from source: https://github.com/diffblue/cbmc"
  case "$(uname -s)" in
    Darwin) hint="brew install cbmc" ;;
    Linux) if [ -f /etc/debian_version ]; then hint="download the ubuntu .deb for your release and architecture from https://github.com/diffblue/cbmc/releases and: sudo apt-get install -y ./cbmc-*.deb"; fi ;;
  esac
  miss "no JBMC: regression and property proofs are off until it is installed ($hint). Behavioural, capability and API contracts work without it."
fi
if command -v gh >/dev/null; then
  if gh auth status >/dev/null 2>&1; then ok "gh: $(gh --version | head -1), authenticated"; else miss "gh is installed but not logged in: run gh auth login"; fi
else miss "no gh (GitHub CLI): needed to read the pull request. https://cli.github.com"; fi
if command -v mvn >/dev/null || command -v gradle >/dev/null; then ok "build tools: $(command -v mvn >/dev/null && echo -n 'mvn ')$(command -v gradle >/dev/null && echo -n gradle)"; else miss "neither mvn nor gradle on the PATH; projects with a wrapper (mvnw, gradlew) build anyway"; fi
if command -v jq >/dev/null; then ok "jq"; else miss "no jq: the fetch script uses it to read the pull request's metadata (https://jqlang.github.io/jq/)"; fi

say "Done. In Claude Code, run:"
echo
case " $SKILLS " in *" verify-bytecode "*)
  echo "    /verify-bytecode https://github.com/apache/commons-numbers/pull/223"
  echo "        Building a pull request runs its build scripts; Claude Code asks for permission first. Every proof is"
  echo "        left under \$TMPDIR/verify-bytecode so you can rerun it." ;;
esac
case " $SKILLS " in *" add-tla-model "*)
  echo "    /add-tla-model com.example.orders.OrderLifecycle#decide \"no two confirmed orders share a seat\""
  echo "        in your own project: adds spec/ with a TLA+ model around that kernel, checks your invariants with TLC," ;
  echo "        and wires the check into the build. The skill shows you what it writes before writing it." ;;
esac
