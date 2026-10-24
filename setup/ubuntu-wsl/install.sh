#!/usr/bin/env bash
# Toolchain installer for Ubuntu 24.04 (native or WSL2), amd64 or arm64.
#
#   setup/ubuntu-wsl/install.sh                  # default components
#   setup/ubuntu-wsl/install.sh jvm provers      # just these
#   setup/ubuntu-wsl/install.sh all              # default + optional
#
# Run as your normal user; the 'system' and 'acl2' components call sudo themselves.
# Idempotent: re-run any time to repair or upgrade.
set -euo pipefail

DEFAULT_COMPONENTS=(system devtools jvm k8s verify provers)
OPTIONAL_COMPONENTS=(rocq isabelle acl2 angr)

BIN="$HOME/.local/bin"
TOOLS="$HOME/tools"
ARCH=$(dpkg --print-architecture)   # amd64 | arm64
case "$ARCH" in
  amd64) UARCH=x86_64;  JAZZER_ARCH=x86-64 ;;
  arm64) UARCH=aarch64; JAZZER_ARCH=arm64 ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }

gh_latest() {  # gh_latest owner/repo -> tag of latest release
  curl -fsSL "https://api.github.com/repos/$1/releases/latest" | jq -r .tag_name
}
gh_asset() {   # gh_asset owner/repo regex -> URL of first matching asset of latest release
  curl -fsSL "https://api.github.com/repos/$1/releases/latest" \
    | jq -er --arg re "$2" '[.assets[] | select(.name | test($re))][0].browser_download_url'
}
wrap_jar() {   # wrap_jar <command> <java args...>: write a launcher into $BIN
  local name=$1; shift
  printf '#!/usr/bin/env bash\nexec java %s "$@"\n' "$*" > "$BIN/$name"
  chmod +x "$BIN/$name"
}
fetch_tar() {  # fetch_tar <url> <dest dir>: replace dest with the archive's contents
  rm -rf "$2"; mkdir -p "$2"
  curl -fsSL "$1" | tar -xz -C "$2"
}
link_bin() {   # link_bin <dir> <binary name>: symlink the first match found under dir
  local found
  found=$(find "$1" -type f -name "$2" -perm -u+x | head -1)
  [[ -n $found ]] || { warn "$2 not found under $1"; return 1; }
  ln -sf "$found" "$BIN/$2"
}
sdkman() { set +u; source "$HOME/.sdkman/bin/sdkman-init.sh"; "$@"; local rc=$?; set -u; return $rc; }

# --------------------------------------------------------------------------- checks
preflight() {
  [[ $EUID -ne 0 ]] || { echo "Run as your normal user, not root (sudo is used where needed)." >&2; exit 1; }
  . /etc/os-release
  [[ ${VERSION_ID:-} == 24.04 ]] || warn "tested on Ubuntu 24.04; this is ${PRETTY_NAME:-unknown}"
  if grep -qi microsoft /proc/version; then
    [[ $(ps -p 1 -o comm=) == systemd ]] || warn "WSL without systemd: add '[boot]\nsystemd=true' to /etc/wsl.conf, then 'wsl --shutdown'"
    [[ $(command -v docker || true) == /mnt/* ]] && warn "'docker' resolves to Docker Desktop's Windows shim; this installs native Docker Engine instead. Quit Docker Desktop (or disable its WSL integration) to avoid two daemons."
  fi
  mkdir -p "$BIN" "$TOOLS"
}

# --------------------------------------------------------------------------- system (sudo)
install_system() {
  step "apt packages (sudo)"
  sudo apt-get update
  sudo apt-get install -y \
    build-essential ca-certificates curl gnupg git jq zip unzip pkg-config zlib1g-dev \
    python3-venv python3-yaml \
    z3 libz3-java graphviz \
    dotnet-sdk-8.0 \
    opam bubblewrap libgmp-dev \
    gcc-riscv64-linux-gnu musl-tools gdb-multiarch binutils-multiarch \
    qemu-user-static binfmt-support

  step "Docker Engine (official repo)"
  . /etc/os-release
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  sudo systemctl enable --now docker

  step "CBMC / JBMC (bounded model checking of C and Java bytecode)"
  local suffix="" deb
  [[ $ARCH == arm64 ]] && suffix="-arm64"
  deb=$(gh_asset diffblue/cbmc "^ubuntu-${VERSION_ID}${suffix}-cbmc-.*-Linux\\.deb$") \
    && curl -fsSLo /tmp/cbmc.deb "$deb" && sudo apt-get install -y /tmp/cbmc.deb && rm -f /tmp/cbmc.deb \
    || warn "no CBMC .deb for Ubuntu $VERSION_ID/$ARCH"

  step "kernel limits for kind (inotify)"
  printf 'fs.inotify.max_user_watches = 524288\nfs.inotify.max_user_instances = 512\n' \
    | sudo tee /etc/sysctl.d/99-kind.conf >/dev/null
  sudo sysctl --system >/dev/null
}

# --------------------------------------------------------------------------- JVM
install_jvm() {
  step "SDKMAN"
  [[ -d $HOME/.sdkman ]] || curl -fsSL "https://get.sdkman.io?rcupdate=true" | bash
  sed -i 's/^sdkman_auto_answer=.*/sdkman_auto_answer=true/' "$HOME/.sdkman/etc/config"

  local list latest
  list=$(sdkman sdk list java)
  latest() { grep -oE "\b$1\.[0-9.+]+-$2\b" <<<"$list" | head -1; }
  local tem25 tem21 graal25
  tem25=$(latest 25 tem); tem21=$(latest 21 tem); graal25=$(latest 25 graalce)

  step "JDKs: $tem25 (default), $tem21, $graal25 (native-image)"
  for v in "$tem21" "$graal25" "$tem25"; do sdkman sdk install java "$v" || true; done
  sdkman sdk default java "$tem25"

  step "Gradle, Maven"
  sdkman sdk install gradle || true
  sdkman sdk install maven || true
}

# --------------------------------------------------------------------------- dev tools
install_devtools() {
  step "jj (Jujutsu VCS, colocated with git)"
  fetch_tar "$(gh_asset jj-vcs/jj "^jj-v.*-$UARCH-unknown-linux-musl\\.tar\\.gz$")" "$TOOLS/jj"
  link_bin "$TOOLS/jj" jj

  step "gh (GitHub CLI)"
  fetch_tar "$(gh_asset cli/cli "^gh_.*_linux_$ARCH\\.tar\\.gz$")" "$TOOLS/gh"
  link_bin "$TOOLS/gh" gh
}

# --------------------------------------------------------------------------- Kubernetes
install_k8s() {
  step "kubectl"
  curl -fsSLo "$BIN/kubectl" "https://dl.k8s.io/release/$(curl -fsSL https://dl.k8s.io/release/stable.txt)/bin/linux/$ARCH/kubectl"
  chmod +x "$BIN/kubectl"

  step "kind"
  curl -fsSLo "$BIN/kind" "https://kind.sigs.k8s.io/dl/$(gh_latest kubernetes-sigs/kind)/kind-linux-$ARCH"
  chmod +x "$BIN/kind"

  step "helm"
  fetch_tar "https://get.helm.sh/helm-$(gh_latest helm/helm)-linux-$ARCH.tar.gz" "$TOOLS/helm"
  link_bin "$TOOLS/helm" helm

  step "k9s"
  fetch_tar "$(gh_asset derailed/k9s "^k9s_Linux_$ARCH\\.tar\\.gz$")" "$TOOLS/k9s"
  link_bin "$TOOLS/k9s" k9s
}

# --------------------------------------------------------------------------- verification tools
install_verify() {
  step "TLA+ tools (TLC, SANY)"
  curl -fsSLo "$TOOLS/tla2tools.jar" https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
  wrap_jar tlc  "-XX:+UseParallelGC -cp $TOOLS/tla2tools.jar tlc2.TLC"
  wrap_jar sany "-cp $TOOLS/tla2tools.jar tla2sany.SANY"

  step "Alloy"
  curl -fsSLo "$TOOLS/alloy.jar" "$(gh_asset AlloyTools/org.alloytools.alloy 'dist\.jar$')"
  wrap_jar alloy "-jar $TOOLS/alloy.jar"

  step "KeY (JML deductive verifier)"
  curl -fsSLo "$TOOLS/key.jar" "$(gh_asset keyproject/key '-exe\.jar$')"
  wrap_jar key "-jar $TOOLS/key.jar"

  step "Jazzer (coverage-guided JVM fuzzer)"
  fetch_tar "$(gh_asset CodeIntelligenceTesting/jazzer "^jazzer-linux-$JAZZER_ARCH\\.tar\\.gz$")" "$TOOLS/jazzer"
  link_bin "$TOOLS/jazzer" jazzer

  step "cvc5 (SMT solver)"
  rm -rf "$TOOLS/cvc5"; mkdir -p "$TOOLS/cvc5"
  curl -fsSLo /tmp/cvc5.zip "$(gh_asset cvc5/cvc5 "^cvc5-Linux-$( [[ $ARCH == arm64 ]] && echo arm64 || echo x86_64 )-static\\.zip$")"
  unzip -q /tmp/cvc5.zip -d "$TOOLS/cvc5" && rm /tmp/cvc5.zip
  link_bin "$TOOLS/cvc5" cvc5

  step "Z3 (upstream release; shadows the older apt z3 on PATH)"
  rm -rf "$TOOLS/z3"; mkdir -p "$TOOLS/z3"
  curl -fsSLo /tmp/z3.zip "$(gh_asset Z3Prover/z3 "^z3-.*-$( [[ $ARCH == arm64 ]] && echo arm64 || echo x64 )-glibc-.*\\.zip$")"
  unzip -q /tmp/z3.zip -d "$TOOLS/z3" && rm /tmp/z3.zip
  link_bin "$TOOLS/z3" z3

  step "Dafny, Boogie (.NET tools)"
  if command -v dotnet >/dev/null; then
    for t in dafny boogie; do
      dotnet tool update --global "$t" >/dev/null 2>&1 || dotnet tool install --global "$t"
    done
  else
    warn "dotnet missing; run the 'system' component first"
  fi
}

# --------------------------------------------------------------------------- proof assistants
install_provers() {
  step "Lean 4 (elan)"
  if [[ ! -x $HOME/.elan/bin/elan ]]; then
    curl -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
      | sh -s -- -y --default-toolchain stable
  else
    "$HOME/.elan/bin/elan" self update || true
    "$HOME/.elan/bin/elan" toolchain install stable
  fi

  step "Sail (ISA spec language; generates Lean/Rocq/Isabelle from RISC-V and Arm specs)"
  fetch_tar "$(gh_asset rems-project/sail "^sail-Linux-$UARCH\\.tar\\.gz$")" "$TOOLS/sail"
  link_bin "$TOOLS/sail" sail
}

install_rocq() {
  step "Rocq via opam (slow: compiles OCaml and Rocq from source)"
  command -v opam >/dev/null || { warn "opam missing; run the 'system' component first"; return 1; }
  [[ -d $HOME/.opam ]] || opam init -y --bare --no-setup
  opam switch list -s | grep -qx rocq || opam switch create rocq ocaml-base-compiler.5.3.0 -y
  opam repo add --switch rocq rocq-released https://rocq-prover.org/opam/released 2>/dev/null || true
  opam install --switch rocq -y rocq-prover
}

install_isabelle() {
  step "Isabelle (bundle ~1 GB; includes Jinja/JinjaThreads JVM semantics via the AFP separately)"
  local tarball
  tarball=$(curl -fsSL https://isabelle.in.tum.de/installation.html \
    | grep -oE 'Isabelle20[0-9]+(-[0-9]+)?_linux\.tar\.gz' | head -1)
  [[ -n $tarball ]] || { warn "could not find the Isabelle Linux bundle"; return 1; }
  if [[ ! -d $TOOLS/${tarball%_linux.tar.gz} ]]; then
    curl -fsSL "https://isabelle.in.tum.de/dist/$tarball" | tar -xz -C "$TOOLS"
  fi
  ln -sf "$TOOLS/${tarball%_linux.tar.gz}/bin/isabelle" "$BIN/isabelle"
}

install_acl2() {
  step "ACL2 (apt; home of the M1-M6 JVM models)"
  sudo apt-get install -y acl2
}

install_angr() {
  step "angr (binary symbolic execution) in $TOOLS/venvs/angr"
  python3 -m venv "$TOOLS/venvs/angr"
  "$TOOLS/venvs/angr/bin/pip" install -q --upgrade pip angr
  printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$TOOLS/venvs/angr/bin/python" > "$BIN/angr-python"
  chmod +x "$BIN/angr-python"
}

# --------------------------------------------------------------------------- shell
install_shellrc() {
  local mark="# >>> formal-verification toolchain >>>"
  grep -qF "$mark" "$HOME/.bashrc" && return
  step "~/.bashrc"
  cat >> "$HOME/.bashrc" <<'EOF'
# >>> formal-verification toolchain >>>
export PATH="$HOME/.local/bin:$HOME/.dotnet/tools:$HOME/.elan/bin:$PATH"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
command -v opam >/dev/null && [[ -d $HOME/.opam ]] && eval "$(opam env --switch=rocq 2>/dev/null)"
command -v kubectl >/dev/null && source <(kubectl completion bash) && alias k=kubectl && complete -o default -F __start_kubectl k
command -v kind >/dev/null && source <(kind completion bash)
command -v helm >/dev/null && source <(helm completion bash)
# <<< formal-verification toolchain <<<
EOF
}

# --------------------------------------------------------------------------- main
usage() {
  echo "usage: $0 [all | component...]"
  echo "  default:  ${DEFAULT_COMPONENTS[*]}"
  echo "  optional: ${OPTIONAL_COMPONENTS[*]}"
}

main() {
  local components=("$@")
  case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "")  components=("${DEFAULT_COMPONENTS[@]}") ;;
    all) components=("${DEFAULT_COMPONENTS[@]}" "${OPTIONAL_COMPONENTS[@]}") ;;
  esac
  preflight
  export PATH="$BIN:$HOME/.dotnet/tools:$HOME/.elan/bin:$PATH"
  for c in "${components[@]}"; do
    declare -F "install_$c" >/dev/null || { usage; exit 1; }
    "install_$c"
  done
  install_shellrc
  step "Done. Open a new shell (docker group + PATH), then run setup/ubuntu-wsl/doctor.sh"
}

main "$@"
