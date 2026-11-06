#!/usr/bin/env bash
# Toolchain installer for Ubuntu 24.04 and 26.04, amd64 or arm64, on a machine, a VM or WSL2.
#
#   examples/setup/ubuntu/install.sh                  # default components
#   examples/setup/ubuntu/install.sh jvm provers      # just these
#   examples/setup/ubuntu/install.sh all              # default + optional
#
# Run as your normal user; the 'system' and 'acl2' components call sudo themselves.
# Idempotent: re-run any time to repair or upgrade.
#
# What differs between the releases is decided in one place, release_profile below; every other step is the same on
# both. WSL needs nothing of its own beyond the two warnings in preflight.
set -euo pipefail

DEFAULT_COMPONENTS=(system devtools jvm k8s verify provers)
OPTIONAL_COMPONENTS=(rocq isabelle acl2 angr)
NODE_VERSION=24.21.0           # LTS; pinned for reproducible wrangler runs

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
    | jq -er --arg re "$2" 'first(.assets[] | select(.name | test($re)) | .browser_download_url)'
}  # no match: no output (not "null"), so a fallback in $(a || b) gets only the other URL
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

# --------------------------------------------------------------------------- releases
# Everything that differs between the supported Ubuntu releases, and only that:
#   DOTNET_PACKAGE        the .NET SDK apt has (Dafny and Boogie are .NET tools)
#   DOTNET_ROLL_FORWARD   launchers that let Dafny and Boogie, built for .NET 8, run on a newer runtime
#   QEMU_PACKAGES         user-mode QEMU with static binaries and binfmt (for the RISC-V examples)
#   CBMC_RELEASES         the Ubuntu releases whose CBMC .deb to try, in order (Diffblue lags behind Ubuntu)
#   GNU_COREUTILS_FIRST   put GNU coreutils ahead of the release's default ones on PATH
release_profile() {
  . /etc/os-release
  case ${VERSION_ID:-} in
    24.04)
      DOTNET_PACKAGE=dotnet-sdk-8.0
      DOTNET_ROLL_FORWARD=false
      QEMU_PACKAGES=(qemu-user-static)
      CBMC_RELEASES=(24.04)
      GNU_COREUTILS_FIRST=false
      ;;
    26.04)
      DOTNET_PACKAGE=dotnet-sdk-10.0                 # 26.04 has no .NET 8
      DOTNET_ROLL_FORWARD=true                       # Boogie refuses to start on .NET 10 without it
      QEMU_PACKAGES=(qemu-user qemu-user-binfmt)     # qemu-user ships the static binaries; -static is gone
      CBMC_RELEASES=(26.04 24.04)
      GNU_COREUTILS_FIRST=true                       # the default coreutils are uutils (see install_gnu_coreutils)
      ;;
    *)
      echo "Unsupported release: ${PRETTY_NAME:-unknown}. This installer knows Ubuntu 24.04 and 26.04;" \
           "add a case to release_profile in $0 for another." >&2
      exit 1
      ;;
  esac
}

# --------------------------------------------------------------------------- checks
preflight() {
  [[ $EUID -ne 0 ]] || { echo "Run as your normal user, not root (sudo is used where needed)." >&2; exit 1; }
  release_profile
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
    python3-venv python3-yaml python3-jsonschema tmux \
    z3 libz3-java graphviz \
    "$DOTNET_PACKAGE" \
    opam bubblewrap libgmp-dev \
    gcc-riscv64-linux-gnu musl-tools gdb-multiarch binutils-multiarch \
    "${QEMU_PACKAGES[@]}" binfmt-support

  step "Docker Engine (official repo)"
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
  local suffix="" deb="" r
  [[ $ARCH == arm64 ]] && suffix="-arm64"
  for r in "${CBMC_RELEASES[@]}"; do
    deb=$(gh_asset diffblue/cbmc "^ubuntu-${r//./\\.}${suffix}-cbmc-.*-Linux\\.deb$" 2>/dev/null) && break
  done
  [[ -n $deb ]] && curl -fsSLo /tmp/cbmc.deb "$deb" && sudo apt-get install -y /tmp/cbmc.deb && rm -f /tmp/cbmc.deb \
    || warn "no CBMC .deb for Ubuntu ${CBMC_RELEASES[*]} on $ARCH"

  [[ $GNU_COREUTILS_FIRST == true ]] && install_gnu_coreutils

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

  step "Node.js $NODE_VERSION (for wrangler / Cloudflare; on WSL, Windows' node under /mnt/c is not usable)"
  local node_arch=$([[ $ARCH == arm64 ]] && echo arm64 || echo x64)
  rm -rf "$TOOLS/node"; mkdir -p "$TOOLS/node"
  curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-$node_arch.tar.xz" \
    | tar -xJ -C "$TOOLS/node" --strip-components=1
  for b in node npm npx; do ln -sf "$TOOLS/node/bin/$b" "$BIN/$b"; done

  step "Rust (rustup, stable; for lib/, the jvmcontract crate)"
  if [[ -x $HOME/.cargo/bin/rustup ]]; then
    "$HOME/.cargo/bin/rustup" update stable
  else
    curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable --no-modify-path
  fi
  for b in cargo rustc rustup; do ln -sf "$HOME/.cargo/bin/$b" "$BIN/$b"; done
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
    # Both are built for .NET 8. Where the release has a newer runtime only, a launcher ahead of ~/.dotnet/tools on
    # PATH lets them roll forward to it.
    if [[ $DOTNET_ROLL_FORWARD == true ]]; then
      for t in dafny boogie; do
        printf '#!/usr/bin/env bash\nDOTNET_ROLL_FORWARD=Major exec %s "$@"\n' "$HOME/.dotnet/tools/$t" > "$BIN/$t"
        chmod +x "$BIN/$t"
      done
    fi
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
GNU_COREUTILS="$HOME/.local/lib/gnu-coreutils"
# Ubuntu 26.04 makes the Rust uutils its coreutils, which differ from GNU in ways jobs notice (timeout exits 124, not
# 137, after -s KILL; tail rejects -15 before several files). build-essential depends on coreutils-from-uutils there,
# so the switch is not made system-wide: GNU's own binaries (gnu-coreutils, as gnutimeout, gnutail, ...) are linked
# under their plain names into one directory that the shell rc puts first on PATH. GNU_COREUTILS_FIRST says where.
install_gnu_coreutils() {
  step "GNU coreutils ahead of uutils on PATH ($GNU_COREUTILS)"
  sudo apt-get install -y gnu-coreutils
  mkdir -p "$GNU_COREUTILS"
  local f
  for f in /usr/bin/gnu*; do
    [[ $(dpkg -S "$f" 2>/dev/null) == gnu-coreutils:* ]] && ln -sfn "$f" "$GNU_COREUTILS/${f##*/gnu}"
  done
}

install_gnu_coreutils_path() {   # after the toolchain block, so GNU's coreutils come before everything else
  local rc mark="# >>> GNU coreutils first >>>"
  [[ $GNU_COREUTILS_FIRST == true && -d $GNU_COREUTILS ]] || return 0
  for rc in "$HOME/.bashrc" "$HOME/.profile" "$HOME/.zshrc"; do   # .profile: a non-interactive login shell stops early in .bashrc
    [[ $rc == *zshrc && ! -f $rc ]] && continue
    grep -qF "$mark" "$rc" 2>/dev/null && continue
    step "${rc/#$HOME/\~}: GNU coreutils first"
    printf '%s\nexport PATH="%s:$PATH"\n# <<< GNU coreutils first <<<\n' "$mark" '$HOME/.local/lib/gnu-coreutils' >> "$rc"
  done
}
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

install_zshrc() {   # a zsh login shell gets the same PATH, so the tools resolve in SSH and agent sessions
  local mark="# >>> formal-verification toolchain >>>"
  [[ -f $HOME/.zshrc || $(getent passwd "$USER" | cut -d: -f7) == */zsh ]] || return 0
  grep -qF "$mark" "$HOME/.zshrc" 2>/dev/null && return
  step "~/.zshrc"
  cat >> "$HOME/.zshrc" <<'EOF'
# >>> formal-verification toolchain >>>
export PATH="$HOME/.local/bin:$HOME/.dotnet/tools:$HOME/.elan/bin:$PATH"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
command -v opam >/dev/null && [[ -d $HOME/.opam ]] && eval "$(opam env --switch=rocq 2>/dev/null)"
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
  install_zshrc
  install_gnu_coreutils_path
  step "Done. Open a new shell (docker group + PATH), then run examples/setup/ubuntu/doctor.sh"
}

main "$@"
