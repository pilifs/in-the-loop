#!/usr/bin/env bash
# Finds the compiled main classes of a Java module without building it, and says how to build it.
#
#   find-classes.sh <project-dir> [module-dir]
#
# Prints KEY=VALUE lines:
#   BUILD      maven, gradle or plain
#   MODULE     the module directory
#   CLASSES    the module's main class directories that exist, PATH-separated (empty: not compiled yet)
#   STALE      1 if a source under src/main is newer than the newest class file, else 0
#   CLASSPATH  the module's dependencies, if a Maven dependency:build-classpath output is lying around (else empty)
#   BUILD_CMD  the command that compiles the module, to run from <project-dir> when CLASSES is empty or STALE=1
#
# Exit 0 when classes exist and are fresh, 1 when they are missing or stale (run BUILD_CMD), 2 on a bad argument.
set -uo pipefail

project=${1:?usage: find-classes.sh <project-dir> [module-dir]}
module=${2:-.}
project=$(cd "$project" && pwd) || exit 2
dir=$project/$module
[ -d "$dir" ] || { echo "find-classes.sh: $dir is not a directory" >&2; exit 2; }

build=plain
build_cmd=""
candidates=()
if [ -f "$project/pom.xml" ] || [ -f "$dir/pom.xml" ]; then
  build=maven
  mvn=mvn; [ -x "$project/mvnw" ] && mvn=./mvnw
  select=""; [ "$module" != "." ] && select="-pl $module -am "
  build_cmd="$mvn -q ${select}compile -DskipTests"
  candidates+=("$dir/target/classes")
else
  for f in settings.gradle settings.gradle.kts build.gradle build.gradle.kts; do
    if [ -f "$project/$f" ] || [ -f "$dir/$f" ]; then build=gradle; fi
  done
  if [ "$build" = gradle ]; then
    gradle=gradle; [ -x "$project/gradlew" ] && gradle=./gradlew
    path=""; [ "$module" != "." ] && path=":${module//\//:}"
    build_cmd="$gradle -q $path:compileJava"
    candidates+=("$dir/build/classes/java/main" "$dir/build/classes/kotlin/main")
  else
    build_cmd="javac -parameters -g -proc:none -d $module/build/main \$(find $module/src/main/java -name '*.java')"
    candidates+=("$dir/build/main" "$dir/build/classes/java/main" "$dir/target/classes" "$dir/out/production/classes" "$dir/classes")
  fi
fi

classes=""
for c in "${candidates[@]}"; do
  if [ -d "$c" ] && [ -n "$(find "$c" -name '*.class' -print -quit 2>/dev/null)" ]; then
    classes="${classes:+$classes:}$c"
  fi
done

stale=0
if [ -n "$classes" ] && [ -d "$dir/src/main" ]; then
  newest_src=$(find "$dir/src/main" -type f \( -name '*.java' -o -name '*.kt' \) -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
  newest_cls=$(find ${classes//:/ } -name '*.class' -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
  if [ -n "$newest_src" ] && [ -n "$newest_cls" ] && [ "${newest_src%.*}" -gt "${newest_cls%.*}" ]; then stale=1; fi
fi

classpath=""
for f in "$dir/target/classpath.txt" "$dir/cp.txt" "$dir/target/cp.txt"; do
  [ -f "$f" ] && { classpath=$(tr -d '\n' < "$f"); break; }
done

echo "BUILD=$build"
echo "MODULE=$module"
echo "CLASSES=$classes"
echo "STALE=$stale"
echo "CLASSPATH=$classpath"
echo "BUILD_CMD=$build_cmd"
[ -n "$classes" ] && [ "$stale" = 0 ]
