#!/usr/bin/env bash
# case_task.sh CASE STEP OUT : one build step of a Spring Boot S case's setup job, offline, on a readiness view of
# the S cache. It is what `scripts/case_job.sh CASE STEP` of that cache ran on 2026-11-27 (the case's jar projects
# and its landed test classes, from the same table, with the same Gradle and the same options), changed in three
# ways so that it can be the task of a readiness operation:
#   - it reads the cache through the view ($SPRING_BOOT_S_CACHE) and writes nothing there: the pin is taken out of
#     the retained worktree with `git archive` into a folder of its own, removed at the end;
#   - Gradle is also given the view's init script (-I "$ITL_READINESS_GRADLE_INIT"), the file repository over what
#     a resolution fetched, and prints its whole log, which is where a resolution reads what the build lacks;
#   - it leaves OUT/tests-STEP.json (the counts of each landed class, by its <testsuite name>) and the JUnit
#     reports under OUT/reports/STEP/, and keeps no jars, classpaths or digests.
# STEP is fix | parent (exit 0 when Gradle exited 0, every landed class present at that pin ran at least one test
# and none failed) or transplant (the parent with the landed test files of the fix: exit 0 when its tests fail or
# do not compile, as case_job.sh has it). S10 and S48 need the network at test time and are not run by this.
set -uo pipefail
c=$1 step=$2 out=$3
cache="${SPRING_BOOT_S_CACHE:?the readiness view of the S cache}"
jdks="$HOME/.sdkman/candidates/java"
mkdir -p "$out"
out=$(cd "$out" && pwd)
IFS=$'\t' read -r _ JM TC CM NET < <(grep -P "^$c\t" "$cache/scripts/cases.tsv")
test -n "${JM:-}" || { echo "no case $c in the cache's cases.tsv"; exit 2; }
test "$NET" = offline || { echo "$c needs the network at test time: not a task this script runs"; exit 2; }
work=$(mktemp -d "$out/.build-$step-XXXXXX")
trap 'rm -rf "$work"' EXIT
tree="$work/tree"
mkdir "$tree"
pin=fix; test "$step" = fix || pin=parent
revision=$(git -C "$cache/worktrees/$c-$pin" rev-parse HEAD) || exit 2
git -C "$cache/worktrees/$c-$pin" archive "$revision" | tar -x -C "$tree"
if test "$step" = transplant; then
  grep -E '/src/(test|testFixtures|intTest|dockerTest)/|^([^/]+/)?[^/]+/build\.gradle$' "$cache/logs/$c-landed-files.txt" | while read -r f; do
    if git -C "$cache/worktrees/$c-fix" cat-file -e "HEAD:$f" 2>/dev/null; then mkdir -p "$tree/$(dirname "$f")"; git -C "$cache/worktrees/$c-fix" show "HEAD:$f" > "$tree/$f"; echo "transplanted $f"
    else rm -f "$tree/$f"; echo "removed $f (deleted by the landing)"; fi
  done
fi
dir() { echo "${1//://}"; }
classfile() { local f; f="$(dir "$1")/src/$2/java/$(echo "$3" | tr . /).java"; test -f "$tree/$f" || f="$(dir "$1")/src/$2/kotlin/$(echo "$3" | tr . /).kt"; echo "$f"; }
tasks="" prev="" results="" classes=""
for t in $TC; do IFS='|' read -r m ss cl mg <<< "$t"
  test -f "$tree/$(classfile "$m" "$ss" "$cl")" || continue
  test "$m:$ss" = "$prev" || tasks="$tasks :$m:$ss"
  tasks="$tasks --tests $cl${mg:+.$mg}"; prev="$m:$ss"
  results="$results $(dir "$m")/build/test-results/$ss"; classes="$classes $(dir "$m")/build/test-results/$ss|$cl"
done
jars=""; test "$step" = transplant || for m in $JM; do jars="$jars :$m:jar"; done
extra=""
case $c in
  S24) extra="-I $cache/scripts/no-werror-micrometer-metrics.init.gradle";;
  S30) extra="-I $cache/scripts/subst-spring-kafka.init.gradle -I $cache/scripts/no-werror-micrometer-metrics.init.gradle";;
esac
v=$(sed -n 's#^distributionUrl=.*gradle-\(.*\)-bin.zip#\1#p' "$tree/gradle/wrapper/gradle-wrapper.properties")
case $v in 9.*) launcher=25.0.5.0+8-tem;; 7.*|8.*) launcher=17.0.21.0+9-tem;; *) launcher=8.0.512.0+9-tem;; esac
paths=""; for name in 8.0.512.0+9-tem 11.0.33.0+10-tem 17.0.21.0+9-tem 21.0.13.0+9-tem 25.0.5.0+8-tem; do paths="$paths$jdks/$name,"; done
# A Gradle home that lasts for the rounds of one resolution, or the steps of one job, and no longer: it holds the
# build's own compiled scripts, and every dependency is read from the view's read-only cache or its file repository.
export JAVA_HOME="$jdks/$launcher" GRADLE_USER_HOME="${ITL_READINESS_SCRATCH:-$out}/.gradle-home" GRADLE_RO_DEP_CACHE="$cache/gradle-home/caches"
mkdir -p "$GRADLE_USER_HOME"
cd "$tree" || exit 2
echo "case=$c step=$step revision=$revision gradle=$v launcher=$launcher tasks=$jars$tasks"
# shellcheck disable=SC2086
"$cache/tools/gradle-$v/bin/gradle" --offline ${ITL_READINESS_GRADLE_INIT:+-I "$ITL_READINESS_GRADLE_INIT"} -I "$cache/scripts/setup-tests.init.gradle" $extra \
  --no-daemon --console=plain --max-workers="${GRADLE_WORKERS:-4}" --no-build-cache -Dorg.gradle.caching=false --no-scan \
  -Porg.gradle.java.installations.auto-detect=false -Porg.gradle.java.installations.auto-download=false \
  "-Porg.gradle.java.installations.paths=${paths%,}" -Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx3g \
  -x :buildSrc:test -x :buildSrc:checkstyleMain -x :buildSrc:checkstyleTest -x :buildSrc:checkFormat --continue $jars $tasks 2>&1 | tee "$work/gradle.log"
rc=${PIPESTATUS[0]}
echo "gradle-exit=$rc"
rm -rf "$out/reports/$step"; mkdir -p "$out/reports/$step"
n=0; for r in $(echo $results | tr ' ' '\n' | sort -u); do n=$((n + 1)); test -d "$r" && mkdir -p "$out/reports/$step/$n" && cp "$r"/TEST-*.xml "$out/reports/$step/$n/" 2>/dev/null; done
python3 -I - "$c" "$step" "$revision" "$v" "$rc" "$out/tests-$step.json" $classes <<'PY'
import glob, json, sys
import xml.etree.ElementTree as E
case, step, revision, gradle, rc, target, *classes = sys.argv[1:]
rows = []
for pair in classes:
    folder, name = pair.split("|")
    row = {"class": name, "suites": 0, "tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for path in sorted(glob.glob(folder + "/TEST-*.xml")):
        root = E.parse(path).getroot()
        if root.get("name", "") == name or root.get("name", "").startswith(name + "$"):
            row["suites"] += 1
            for key in ("tests", "failures", "errors", "skipped"):
                row[key] += int(root.get(key, 0))
    rows.append(row)
record = {"case": case, "step": step, "revision": revision, "gradle": gradle, "gradleExit": int(rc), "classes": rows}
open(target, "w").write(json.dumps(record, sort_keys=True) + "\n")
print(json.dumps(record, sort_keys=True))
ran = all(r["tests"] > 0 for r in rows)
bad = sum(r["failures"] + r["errors"] for r in rows)
if step == "transplant":
    sys.exit(0 if bad else 3)             # 3: the caller decides between "does not compile" and "did not fail"
sys.exit(0 if int(rc) == 0 and ran and not bad else 1)
PY
said=$?
if test "$step" = transplant; then
  if test $said = 0; then echo TRANSPLANT-FAILS-AS-EXPECTED; exit 0; fi
  if test $rc != 0 && grep -qE 'compile(Test|IntTest|DockerTest|TestFixtures)(Java|Kotlin) FAILED' "$work/gradle.log"; then
    grep -E '\.(java|kt):[0-9]+: error:|^e: ' "$work/gradle.log" | head -5; echo TRANSPLANT-DOES-NOT-COMPILE-AS-EXPECTED; exit 0
  fi
  echo "TRANSPLANT DID NOT FAIL (gradle-exit=$rc)"; exit 1
fi
exit $said
