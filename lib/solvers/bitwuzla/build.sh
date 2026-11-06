#!/usr/bin/env bash
# Build a pinned Bitwuzla release from source, for Phase 6 of llm-dlc/loops/engine-priorities.md, and record what was
# built. Run as a pipeline job (it fetches from the network and takes minutes), from the repository root:
#
#   lib/solvers/bitwuzla/build.sh VERSION [PREFIX_ROOT]
#
# - VERSION is a release tag of github.com/bitwuzla/bitwuzla (0.8.2, say). If the tag does not exist, the script
#   lists the release tags it found and exits 3, so a resubmit can pin one of them.
# - It installs into PREFIX_ROOT/bitwuzla-VERSION (default ~/tools/bitwuzla, next to ~/tools/z3 and ~/tools/cvc5),
#   built shared, with the C API's headers and pkg-config file, and points PREFIX_ROOT/current at it. Nothing else on
#   the machine changes: meson and ninja come from a venv in the work directory.
# - It writes lib/solvers/bitwuzla/build.json: the version, the tag's commit, the source tarball's sha256, the CaDiCaL
#   and other subprojects it links (from their wrap files, with their digests), GMP, the compiler, the build tools,
#   the machine, and what the smoke tests answered.
# - The smoke tests are three SMT-LIB queries with known answers (bit-vector sat, bit-vector unsat, an array) and a C
#   program linked against the installed library through pkg-config, which prints the library's version.
set -euo pipefail

VERSION=${1:?usage: build.sh VERSION [PREFIX_ROOT]}
PREFIX_ROOT=${2:-$HOME/tools/bitwuzla}
REPO=https://github.com/bitwuzla/bitwuzla
HERE=$(cd "$(dirname "$0")" && pwd)
RECORD=$HERE/build.json
WORK=$(mktemp -d "${TMPDIR:-/tmp}/bitwuzla-build.XXXXXX")
JOBS=${VERIFY_CPUS:-$(nproc)}
JOBS=${JOBS%.*}
log() { printf '[bitwuzla] %s\n' "$*"; }

log "version $VERSION, work directory $WORK, $JOBS parallel jobs, install under $PREFIX_ROOT"

# The tag, and the commit it names. An annotated tag is peeled (^{}).
TAGS=$(git ls-remote --tags "$REPO")
TAG=""
for t in "$VERSION" "v$VERSION"; do
  if grep -q "refs/tags/$t\$" <<<"$TAGS"; then TAG=$t; break; fi
done
if [[ -z $TAG ]]; then
  log "no tag $VERSION (or v$VERSION) in $REPO. Its latest tags:"
  sed -n 's#.*refs/tags/\([^^]*\)$#\1#p' <<<"$TAGS" | sort -V | tail -20
  exit 3
fi
COMMIT=$(grep "refs/tags/$TAG^{}\$" <<<"$TAGS" | cut -f1 || true)
[[ -n $COMMIT ]] || COMMIT=$(grep "refs/tags/$TAG\$" <<<"$TAGS" | cut -f1)
log "tag $TAG is commit $COMMIT"

# The release's source, by its tarball, whose digest is recorded.
TARBALL_URL=$REPO/archive/refs/tags/$TAG.tar.gz
curl -fsSL --retry 3 -o "$WORK/src.tar.gz" "$TARBALL_URL"
TARBALL_SHA256=$(sha256sum "$WORK/src.tar.gz" | cut -d' ' -f1)
log "source $TARBALL_URL, sha256 $TARBALL_SHA256"
mkdir "$WORK/src"
tar -xzf "$WORK/src.tar.gz" -C "$WORK/src" --strip-components=1

# Build tools, in a venv of their own: the machine has neither meson nor ninja.
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet --disable-pip-version-check meson ninja
export PATH=$WORK/venv/bin:$PATH
MESON_VERSION=$(meson --version)
NINJA_VERSION=$(ninja --version)
log "meson $MESON_VERSION, ninja $NINJA_VERSION"

# Configure, build, and install into a staging directory that is then moved into place, so a failed build leaves no
# half install. meson is called directly rather than through configure.py, whose options change between releases:
# a release build, the library shared (for the C API), the subprojects (CaDiCaL, SymFPU) fetched by their wrap files.
DEST=$PREFIX_ROOT/bitwuzla-$VERSION
STAGE=$PREFIX_ROOT/.bitwuzla-$VERSION.partial
mkdir -p "$PREFIX_ROOT"
rm -rf "${STAGE:?}"
cd "$WORK/src"
SETUP=(meson setup build --buildtype=release --prefix "$DEST" -Ddefault_library=shared --wrap-mode=default)
log "configure: ${SETUP[*]}"
"${SETUP[@]}"
cd build
meson compile -j "$JOBS"
DESTDIR=$STAGE meson install --quiet
rm -rf "${DEST:?}"
mv "$STAGE$DEST" "$DEST"
rm -rf "${STAGE:?}"
ln -sfn "bitwuzla-$VERSION" "$PREFIX_ROOT/current"
log "installed in $DEST ($PREFIX_ROOT/current)"

BIN=$DEST/bin/bitwuzla
# Meson drops the build's rpath on install, so the library's directory goes on LD_LIBRARY_PATH (recorded as libDir).
LIB_DIR=$(dirname "$(find "$DEST" -name 'libbitwuzla.so*' -print -quit)")
export LD_LIBRARY_PATH=$LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
BIN_VERSION=$("$BIN" --version)
log "bitwuzla --version: $BIN_VERSION"

# Smoke tests, with answers known by hand.
smt() { printf '%s\n' "$1" > "$WORK/q.smt2"; { "$BIN" "$WORK/q.smt2" || true; } | head -1; }
SAT_BV=$(smt '(set-logic QF_BV)(declare-const x (_ BitVec 32))(assert (= (bvmul x #x00000003) #x00000001))(check-sat)')
UNSAT_BV=$(smt '(set-logic QF_BV)(declare-const x (_ BitVec 32))(assert (not (= (bvadd x x) (bvshl x #x00000001))))(check-sat)')
UNSAT_ARRAY=$(smt '(set-logic QF_ABV)(declare-const a (Array (_ BitVec 32) (_ BitVec 32)))(declare-const i (_ BitVec 32))(declare-const v (_ BitVec 32))(assert (not (= (select (store a i v) i) v)))(check-sat)')
log "3x = 1 over 32 bits: $SAT_BV (expected sat); not x + x = x << 1: $UNSAT_BV (expected unsat); not read over write: $UNSAT_ARRAY (expected unsat)"

cat > "$WORK/capi.c" <<'C'
#include <bitwuzla/c/bitwuzla.h>
#include <stdio.h>
int main(void) { printf("%s %s\n", bitwuzla_version(), bitwuzla_git_id()); return 0; }
C
PKG_CONFIG_PATH=$(dirname "$(find "$DEST" -name bitwuzla.pc -print -quit)")
export PKG_CONFIG_PATH
# shellcheck disable=SC2046
cc "$WORK/capi.c" -o "$WORK/capi" $(pkg-config --cflags --libs bitwuzla)
CAPI=$("$WORK/capi")
log "C API through pkg-config: $CAPI"

SAT_SOLVERS=$("$BIN" --help 2>&1 | grep -A3 -- '--sat-solver' | tr -s ' \n' ' ' || true)

# The record, read from the environment rather than interpolated into the program, so no value can break its quoting.
export VERSION TAG COMMIT TARBALL_URL TARBALL_SHA256 BIN_VERSION CAPI DEST LIB_DIR PKG_CONFIG_PATH SAT_SOLVERS \
  MESON_VERSION NINJA_VERSION SAT_BV UNSAT_BV UNSAT_ARRAY WORK
SETUP_LINE="${SETUP[*]}" python3 - "$RECORD" <<'PY'
import configparser, glob, json, os, platform, subprocess, sys
e = os.environ
src = os.path.join(e["WORK"], "src")
def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""
def home(path):
    # Paths under the home directory are recorded from ~, so the record names no user.
    h = e["HOME"].rstrip("/")
    return "~" + path[len(h):] if path == h or path.startswith(h + "/") else path
subprojects = {}
for wrap in sorted(glob.glob(os.path.join(src, "subprojects", "*.wrap"))):
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(wrap)
    for section in cp.sections():
        subprojects[os.path.basename(wrap)[:-5]] = {"kind": section, **dict(cp[section])}
fetched = sorted(os.path.basename(p) for p in glob.glob(os.path.join(src, "subprojects", "*"))
                 if os.path.isdir(p) and os.path.basename(p) not in ("packagefiles", "packagecache"))
record = {
    "tool": "bitwuzla",
    "version": e["VERSION"],
    "tag": e["TAG"],
    "commit": e["COMMIT"],
    "source": {"url": e["TARBALL_URL"], "sha256": e["TARBALL_SHA256"]},
    "binaryVersion": e["BIN_VERSION"],
    "capi": e["CAPI"],
    "configure": e["SETUP_LINE"].replace(e["DEST"], "<install>"),
    "install": home(e["DEST"]),
    "libDir": home(e["LIB_DIR"]),
    "pkgConfigPath": home(e["PKG_CONFIG_PATH"]),
    "subprojects": subprojects,
    "subprojectsFetched": fetched,
    "satSolvers": e["SAT_SOLVERS"],
    "gmp": {"package": "libgmp-dev", "version": run("dpkg-query", "-W", "-f", "${Version}", "libgmp-dev")},
    "compiler": (run("c++", "--version").splitlines() or [""])[0],
    "buildTools": {"meson": e["MESON_VERSION"], "ninja": e["NINJA_VERSION"], "python": platform.python_version()},
    "machine": {"arch": platform.machine(), "system": platform.system(), "release": platform.release(),
                "job": e.get("VERIFY_JOB_ID")},
    "smoke": {"bvSat": e["SAT_BV"], "bvUnsat": e["UNSAT_BV"], "arrayUnsat": e["UNSAT_ARRAY"]},
}
with open(sys.argv[1], "w") as f:
    json.dump(record, f, indent=2)
    f.write("\n")
PY
log "wrote $RECORD"

if [[ $SAT_BV != sat || $UNSAT_BV != unsat || $UNSAT_ARRAY != unsat ]]; then
  log "a smoke test gave the wrong answer"
  exit 1
fi
rm -rf "${WORK:?}"
log "done"
