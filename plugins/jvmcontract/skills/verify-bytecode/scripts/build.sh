#!/usr/bin/env bash
# Compiles one module of a checked-out Maven or Gradle project and prints where its classes and dependencies are.
#
#   build.sh <tree-dir> [module-dir]
#
# <tree-dir> is a checkout (fetch-pr.sh's BASE_DIR or HEAD_DIR); <module-dir> is the module's directory relative to
# it, "." for a single-module build. Prints KEY=VALUE lines:
#
#   BUILD      maven or gradle
#   CLASSES    the module's compiled main classes (a directory; several, PATH-separated, if the build has them)
#   CLASSPATH  the jars and directories the module compiles against, PATH-separated (may be empty)
#   LOG        the build's full output
#
# Exit 0 when the classes exist afterwards, 1 when the build failed (read LOG), 3 when the build tool is unknown.
# This runs the project's own build scripts, which is running the pull request's code: only do it for a pull
# request you would also build locally.
set -uo pipefail

tree=${1:?usage: build.sh <tree-dir> [module-dir]}
module=${2:-.}
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
tree=$(cd "$tree" && pwd) || exit 2
name=$(basename "$tree")
log=$tree/../build-$name-$(echo "$module" | tr '/.' '__').log
: > "$log"

finish() {
  local classes=$1 classpath=$2
  echo "BUILD=$BUILD"
  echo "CLASSES=$classes"
  echo "CLASSPATH=$classpath"
  echo "LOG=$log"
  for dir in ${classes//:/ }; do
    [ -d "$dir" ] && [ -n "$(find "$dir" -name '*.class' -print -quit)" ] && return 0
  done
  echo "build.sh: no class files under '$classes'; see $log" >&2
  return 1
}

if [ -f "$tree/pom.xml" ]; then
  BUILD=maven
  mvn=mvn
  [ -x "$tree/mvnw" ] && mvn=./mvnw
  skip=(-DskipTests -Dmaven.test.skip=true -Dmaven.javadoc.skip=true -Denforcer.skip=true -Dcheckstyle.skip=true
        -Dspotbugs.skip=true -Dpmd.skip=true -Dcpd.skip=true -Dspotless.check.skip=true -Dforbiddenapis.skip=true
        -Danimal.sniffer.skip=true -Drat.skip=true -Djacoco.skip=true -Dlicense.skip=true -Dmaven.gitcommitid.skip=true)
  select=()
  [ "$module" != "." ] && select=(-pl "$module" -am)
  (cd "$tree" && $mvn -B -q "${select[@]}" compile "${skip[@]}") >>"$log" 2>&1
  status=$?
  cpfile=$tree/../classpath-$name-$(echo "$module" | tr '/.' '__').txt
  select=()
  [ "$module" != "." ] && select=(-pl "$module")
  (cd "$tree" && $mvn -B -q "${select[@]}" dependency:build-classpath -Dmdep.includeScope=compile -Dmdep.outputFile="$cpfile" "${skip[@]}") >>"$log" 2>&1 || true
  classpath=$(cat "$cpfile" 2>/dev/null || true)
  [ $status -ne 0 ] && echo "build.sh: mvn compile exited with $status; see $log" >&2
  finish "$tree/$module/target/classes" "$classpath"
  exit $?
fi

gradle_build=
for f in settings.gradle settings.gradle.kts build.gradle build.gradle.kts; do
  [ -f "$tree/$f" ] && gradle_build=1
done
if [ -n "$gradle_build" ]; then
  BUILD=gradle
  gradle=gradle
  [ -x "$tree/gradlew" ] && gradle=./gradlew
  path=""
  if [ "$module" != "." ]; then
    path=":${module//\//:}"
  fi
  out=$(cd "$tree" && $gradle -q --console=plain --no-daemon -I "$here/gradle-classpath.gradle" "$path:jvmcontractClasspath" 2>>"$log")
  status=$?
  printf '%s\n' "$out" >>"$log"
  classes=$(printf '%s\n' "$out" | sed -n 's/^CLASSES=//p' | tail -1)
  classpath=$(printf '%s\n' "$out" | sed -n 's/^CLASSPATH=//p' | tail -1)
  [ $status -ne 0 ] && echo "build.sh: gradle exited with $status; see $log" >&2
  finish "${classes:-$tree/$module/build/classes/java/main}" "$classpath"
  exit $?
fi

BUILD=unknown
echo "build.sh: no pom.xml or Gradle build in $tree" >&2
echo "BUILD=unknown"
echo "LOG=$log"
exit 3
