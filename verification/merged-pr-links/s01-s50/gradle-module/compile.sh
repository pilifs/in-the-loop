#!/usr/bin/env bash
# Compile Spring Boot's core module at S48's parent pin with Gradle offline, on a readiness view of the S cache.
# The task of readiness-operation.json beside this file, run the same way by the resolution's rounds and by the
# consumer. It writes compiled.json: the pin, how many classes were compiled, and the digest of one of them.
#
# Gradle is given the view's init script (-I "$ITL_READINESS_GRADLE_INIT"), which adds a file repository over the
# view's Maven-layout folder: a module the resolution fetched is read from there, since Gradle's own cache has no
# record of it. Everything the run writes is under a folder of its own, removed at the end.
set -euo pipefail
cache="${SPRING_BOOT_S_CACHE:?the readiness view of the S cache}"
out="${ITL_READINESS_OUT:-$PWD}"
pin=d34a479879d348a1758196b7d1c696ea4f8ea8f0
jdks="$HOME/.sdkman/candidates/java"
paths=""
for name in 8.0.512.0+9-tem 11.0.33.0+10-tem 17.0.21.0+9-tem 21.0.13.0+9-tem 25.0.5.0+8-tem; do paths="$paths$jdks/$name,"; done
test "$(git -C "$cache/worktrees/S48-parent" rev-parse HEAD)" = "$pin" || { echo "wrong upstream revision"; exit 2; }
work=$(mktemp -d "$out/compile-XXXXXX")
trap 'rm -rf "$work"' EXIT
mkdir "$work/tree"
git -C "$cache/worktrees/S48-parent" archive "$pin" | tar -x -C "$work/tree"
export JAVA_HOME="$jdks/25.0.5.0+8-tem" GRADLE_USER_HOME="$work/gradle" GRADLE_RO_DEP_CACHE="$cache/gradle-home/caches"
cd "$work/tree"
"$cache/tools/gradle-9.7.0/bin/gradle" --offline -I "$ITL_READINESS_GRADLE_INIT" --console=plain --no-daemon --no-build-cache --no-scan \
  --max-workers=3 "-Dorg.gradle.jvmargs=-Xmx2g -XX:ActiveProcessorCount=3" -Pkotlin.compiler.execution.strategy=in-process \
  -Porg.gradle.java.installations.auto-detect=false -Porg.gradle.java.installations.auto-download=false \
  "-Porg.gradle.java.installations.paths=${paths%,}" \
  -x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x :buildSrc:checkFormat \
  :core:spring-boot:compileJava
classes=core/spring-boot/build/classes/java/main
one=org/springframework/boot/SpringApplication.class
# Neither of Gradle's caches may hold the withheld module: then it was read from the file repository and nowhere else.
if find "$GRADLE_USER_HOME/caches" "$GRADLE_RO_DEP_CACHE/modules-2/files-2.1" -path '*org.jspecify/jspecify*' -name '*.jar' 2>/dev/null | grep -q .; then
  echo "a Gradle cache holds the withheld module: the file repository was not what supplied it"; exit 3
fi
python3 - "$pin" "$classes" "$one" > "$out/compiled.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
pin, classes, one = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
print(json.dumps({"revision": pin, "task": ":core:spring-boot:compileJava", "classes": sum(1 for _ in classes.rglob("*.class")),
                  "class": one, "sha256": hashlib.sha256((classes / one).read_bytes()).hexdigest(),
                  "withheldModuleInAGradleCache": False}, sort_keys=True))
PY
cat "$out/compiled.json"
