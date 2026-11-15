#!/usr/bin/env bash
# Runs a command with JBMC absent: gate A8 of llm-dlc/loops/example-targets-acceptance.md ("the new native tasks run
# with JBMC absent") and its adversarial row "Native execution without JBMC installed: works for supported tasks; no
# hidden mandatory dependency".
#
#   examples/tools/targets/without_jbmc.sh COMMAND [ARG ...]
#
# Every jbmc executable the command could find (on $PATH, and in /usr/local/bin, /usr/bin and /bin, which the target
# route's verifier and controls put on their own fixed PATH) is covered, in a private mount namespace (bwrap), by
# /dev/null: it still has a name, but it can't be run, and Python's shutil.which no longer finds it. Nothing outside
# the command changes, and the rest of the file system is the same. Before running the command, it checks that jbmc
# can't be run and isn't found, and stops with exit 2 otherwise, so a pass is never a run that had JBMC after all.
set -euo pipefail
if [ $# -eq 0 ]; then
    echo "usage: without_jbmc.sh COMMAND [ARG ...]" >&2
    exit 2
fi
if [ "${WITHOUT_JBMC_INSIDE:-}" = 1 ]; then
    if python3 -c 'import shutil, sys; sys.exit(0 if shutil.which("jbmc") is None else 1)' \
            && ! jbmc --version > /dev/null 2>&1 && ! /usr/bin/jbmc --version > /dev/null 2>&1; then
        echo "without_jbmc.sh: JBMC absent (no runnable jbmc; shutil.which finds none): $*"
    else
        echo "without_jbmc.sh: jbmc can still be run or found, so nothing was run" >&2
        exit 2
    fi
    unset WITHOUT_JBMC_INSIDE
    exec "$@"
fi
binds=()
declare -A seen=()
IFS=: read -r -a dirs <<< "${PATH}:/usr/local/bin:/usr/bin:/bin"
for d in "${dirs[@]}"; do
    [ -n "$d" ] && [ -e "$d/jbmc" ] || continue
    real=$(readlink -f "$d/jbmc")
    [ -n "${seen[$real]:-}" ] && continue
    seen[$real]=1
    binds+=(--ro-bind /dev/null "$real")
done
WITHOUT_JBMC_INSIDE=1 exec bwrap --dev-bind / / "${binds[@]}" -- "$0" "$@"
