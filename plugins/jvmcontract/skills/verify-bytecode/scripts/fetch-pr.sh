#!/usr/bin/env bash
# Fetches a GitHub pull request as two checkouts, the merge base and the head, so both can be compiled and compared.
#
#   fetch-pr.sh <pr> [workdir]
#
# <pr> is https://github.com/OWNER/REPO/pull/N, OWNER/REPO#N, or N for a pull request of the repository in the
# current directory. The default workdir is $TMPDIR/verify-bytecode/OWNER-REPO-N. Prints KEY=VALUE lines:
#
#   WORK        the workdir
#   REPO        OWNER/REPO
#   NUMBER      N
#   BASE_SHA    the tip of the base branch when fetched
#   HEAD_SHA    the pull request's head commit
#   MERGE_BASE  the commit the pull request branched from; the "before" of every comparison
#   BASE_DIR    a checkout of MERGE_BASE
#   HEAD_DIR    a checkout of HEAD_SHA
#   PR_JSON     the pull request's metadata from `gh pr view --json`
#   CHANGED     one changed path per line
#
# Needs git and an authenticated gh. The checkouts are untrusted code: nothing in them is executed here.
set -euo pipefail

pr=${1:?usage: fetch-pr.sh <pr> [workdir]}
case "$pr" in
  https://github.com/*/*/pull/*)
    rest=${pr#https://github.com/}
    repo=${rest%%/pull/*}
    number=${rest##*/pull/}
    number=${number%%[^0-9]*}
    ;;
  *#[0-9]*)
    repo=${pr%#*}
    number=${pr#*#}
    ;;
  [0-9]*)
    repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
    number=$pr
    ;;
  *)
    echo "fetch-pr.sh: cannot read a pull request from '$pr'" >&2
    exit 2
    ;;
esac
[[ "$number" =~ ^[0-9]+$ ]] || { echo "fetch-pr.sh: '$number' is not a pull request number" >&2; exit 2; }

work=${2:-${TMPDIR:-/tmp}/verify-bytecode/${repo//\//-}-$number}
mkdir -p "$work"
work=$(cd "$work" && pwd)

gh pr view "$number" --repo "$repo" \
  --json number,title,body,url,state,isDraft,author,baseRefName,baseRefOid,headRefName,headRefOid,headRepository,headRepositoryOwner,isCrossRepository,additions,deletions,changedFiles,files,labels,mergeable \
  > "$work/pr.json"
base_ref=$(jq -r .baseRefName "$work/pr.json")
base_sha=$(jq -r .baseRefOid "$work/pr.json")
head_sha=$(jq -r .headRefOid "$work/pr.json")

if [ ! -d "$work/repo/.git" ]; then
  rm -rf "$work/repo"
  gh repo clone "$repo" "$work/repo" -- --filter=blob:none --no-checkout --quiet
fi
git -C "$work/repo" fetch --quiet --no-tags origin "$base_ref" "+refs/pull/$number/head:refs/remotes/pr/$number"
merge_base=$(git -C "$work/repo" merge-base "$base_sha" "$head_sha")

for tree in base head; do
  dir=$work/$tree
  if [ -d "$dir" ]; then
    git -C "$work/repo" worktree remove --force "$dir" 2>/dev/null || rm -rf "$dir"
  fi
done
git -C "$work/repo" worktree prune
git -C "$work/repo" worktree add --quiet --detach "$work/base" "$merge_base"
git -C "$work/repo" worktree add --quiet --detach "$work/head" "$head_sha"

git -C "$work/repo" diff --name-only "$merge_base" "$head_sha" > "$work/changed-files.txt"
git -C "$work/repo" diff --stat "$merge_base" "$head_sha" > "$work/diff.stat"
git -C "$work/repo" diff "$merge_base" "$head_sha" > "$work/diff.patch"

echo "WORK=$work"
echo "REPO=$repo"
echo "NUMBER=$number"
echo "BASE_SHA=$base_sha"
echo "HEAD_SHA=$head_sha"
echo "MERGE_BASE=$merge_base"
echo "BASE_DIR=$work/base"
echo "HEAD_DIR=$work/head"
echo "PR_JSON=$work/pr.json"
echo "CHANGED=$work/changed-files.txt"
echo "DIFF=$work/diff.patch"
