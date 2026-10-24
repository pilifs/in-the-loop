#!/usr/bin/env bash
# Report which tools from install.sh are present and working.
# Exit status is non-zero if any *default* component tool is missing.
export PATH="$HOME/.local/bin:$HOME/.dotnet/tools:$HOME/.elan/bin:$PATH"
[[ -s $HOME/.sdkman/bin/sdkman-init.sh ]] && { set +u; source "$HOME/.sdkman/bin/sdkman-init.sh"; }
[[ -d $HOME/.opam ]] && eval "$(opam env --switch=rocq 2>/dev/null)"

fail=0
check() {  # check <required|optional> <name> <shell snippet printing a version>
  local req=$1 name=$2 out rc
  out=$(bash -o pipefail -c "$3" 2>&1); rc=$?
  out=$(grep -m1 . <<<"$out")
  if [[ $rc -eq 0 && -n $out ]]; then
    printf '  \033[32mok\033[0m    %-12s %s\n' "$name" "$out"
  elif [[ $req == required ]]; then
    printf '  \033[31mFAIL\033[0m  %-12s %s\n' "$name" "${out:-not found}"; fail=1
  else
    printf '  \033[2m--    %-12s (optional, not installed)\033[0m\n' "$name"
  fi
}

echo "JVM"
check required java     "java -version"
check required graalvm  "ls -d ~/.sdkman/candidates/java/*graal*/bin/native-image | head -1"
check required gradle   "gradle --version | grep ^Gradle"
check required maven    "mvn -v"
echo "Dev tools"
check required jj       "jj --version"
check required gh       "gh --version"
check optional langfuse "curl -fsS http://localhost:3000/api/public/health"
echo "Containers / Kubernetes"
check required docker   "docker version --format 'client {{.Client.Version}}, server {{.Server.Version}}'"
check required kubectl  "kubectl version --client | head -1"
check required kind     "kind version"
check required helm     "helm version --short"
check required k9s      "k9s version --short | grep -i version"
echo "Solvers / verifiers"
check required z3       "z3 --version"
check required cvc5     "cvc5 --version | head -1"
check required tlc      "(java -cp ~/tools/tla2tools.jar tlc2.TLC -h || true) | grep -m1 -o 'TLC.*Version.*'"
check required alloy    "test -f ~/tools/alloy.jar && echo ~/tools/alloy.jar"
check required key      "test -f ~/tools/key.jar && echo ~/tools/key.jar"
check required dafny    "dafny --version"
check required boogie   "boogie /version"
check required cbmc     "cbmc --version"
check required jbmc     "jbmc --version"
check required jazzer   "test -x ~/tools/jazzer/jazzer && echo ~/tools/jazzer/jazzer"
echo "Proof assistants / ISA specs"
check required lean     "lean --version"
check required lake     "lake --version"
check required sail     "sail --version"
check optional rocq     "rocq --version 2>/dev/null || coqc --version"
check optional isabelle "isabelle version"
check optional acl2     "command -v acl2"
check optional angr     "angr-python -c 'import angr; print(\"angr\", angr.__version__)'"
echo "Native / cross"
check required riscv-gcc "riscv64-linux-gnu-gcc --version"
check required qemu-rv64 "qemu-riscv64-static --version"
check required musl-gcc "command -v musl-gcc"
check required zlib-dev "dpkg-query -W -f='zlib1g-dev \${Version}\\n' zlib1g-dev"   # native-image links -lz

exit $fail
