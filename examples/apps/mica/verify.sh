#!/usr/bin/env bash
# Compiles the Mica module, runs its tests, and runs every check jvmcontract provides for it: the behavioural,
# capability and API contracts, the property proofs (JBMC), and the class-initialization model (TLC, with
# deadlock checking).
# Needs javac and java on the PATH, jvmcontract (on the PATH, or $JVMCONTRACT, or built in ../../../lib), jbmc, and
# tla2tools.jar in ~/tools or $TLA2TOOLS_JAR.
set -euo pipefail
cd "$(dirname "$0")"

JVMCONTRACT="${JVMCONTRACT:-$(command -v jvmcontract || echo ../../../lib/target/release/jvmcontract)}"
if [ ! -x "$JVMCONTRACT" ]; then
    echo "jvmcontract not found: cargo build --release --manifest-path ../../../lib/Cargo.toml, or set JVMCONTRACT" >&2
    exit 2
fi

rm -rf build
javac -parameters -g -proc:none -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -proc:none -cp build/main -d build/test $(find src/test/java -name '*.java')
java -ea -cp "build/main:build/test" net.terminalvalue.mica.Tests

"$JVMCONTRACT" verify --contracts src/contract --classes build/main --module mica --sources src/main/java --report build/reports
"$JVMCONTRACT" prove --properties src/contract/properties.contract --classes build/main --sources src/main/java --report build/reports
"$JVMCONTRACT" tla src/contract/ClassInitialization.decide.contract spec/ClassInitContract.tla
"$JVMCONTRACT" tlc spec/ClassInit.tla --deadlock --library ../../tools/tla/standard-modules
