"""`sync.py promote`: move the remote `main` to a tested, frozen part of `develop`, with its evidence accounted for.

A promotion is the slow, careful counterpart of a checkpoint (checkpoint.py). It says of one commit of `develop`:
this code passed the default test run, the logs its commits point at are published, and the originals behind it are
in the private archive. It is one transaction, written down as it goes, so that a restart continues it:

  1. P is the remote's `main` as the remote gives it, D the revision named, which must already be on the remote's
     `develop`. The frozen set is `ancestors(D) - ancestors(P)`, merge parents included. What lands on `develop`
     afterwards belongs to the next promotion. A `main` that is not an ancestor of D was moved by someone else: the
     line takes it in by an ordinary merge, is checkpointed, and that merge is promoted.
  2. The candidate is built in a jj workspace of its own (`REPO-promote`, kept between promotions), by that
     checkout's own tools: the logs of the frozen commits are taken from the workspaces that hold them, checked,
     uploaded, and the generated overview is written. Nobody's working copy is read or changed.
  3. Every `LLM-Trace` of a frozen commit must then resolve to a published or withdrawn log, and every original of
     the frozen jobs and sessions must be verified in the private archive, or be a recorded gap. One that is
     neither blocks the candidate and is named; `develop` goes on meanwhile.
  4. The publication record is a commit C of its own on D: the log URLs, the regenerated index and overview, and one
     small summary, `llm-dlc/artifacts/YYYY/MM/DD/promotion-ID.json`, which names the private inventory (every
     commit, trailer and occurrence the promotion covers) by its occurrence and digest.
  5. The gate is asked of C's tree: a passed default run that covers it (lib/tools/default_run.py), or one run
     here, in the candidate. Its record and log are sealed in the archive and verified there before `main` moves;
     the receipt is kept outside the tree, so the tested tree never has to hold its own result.
  6. `main` is pushed to C only if it is still P, forward only; a lost answer is settled by reading the remote.
     `develop` then goes forward to C, or, when it moved meanwhile, takes C in by an ordinary merge.
  7. The receipt names P, D, C, the tree, the gate and what the remote answered.

`--dry-run` prints the review view and what would block, and changes nothing. `--skip-tests REASON` is the user's
alone, as for a push.

The module is given sync.py's own module object (`s`), since sync.py runs as __main__.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import checkpoint
from checkpoint import DEVELOP, MAIN, REMOTE, git, have, is_ancestor, jq, remote_ref

SCHEMA = "itl-promotion/v1"
SUMMARY_SCHEMA = "itl-publication-summary/v1"
INVENTORY_SCHEMA = "itl-promotion-inventory/v1"
GATE_SCHEMA = "itl-promotion-gate/v1"
SUMMARY_MAX = 64 << 10       # a summary in git; more goes to the private inventory
ARTIFACTS = "llm-dlc/artifacts"
WORKSPACE = "promote"
# What a publication record may change: generated records, never a source file. llm-dlc/README.md is in it for
# its generated session table alone (default_run.covers checks that nothing else in it differs).
RECORDS = ("llm-dlc/traces/", "llm-dlc/index.json", ARTIFACTS + "/", "llm-dlc/decisions/", "llm-dlc/README.md")
# Paths a reviewer of the source diff does not page through: records of what ran.
GENERATED = RECORDS + ("verification/results/", "verification/jobs/")
EXAMPLE_RECORDS = re.compile(r"examples/[^/]+/records/")  # an example's replay records: evidence, not source
VERIFIED = ("remote_verified", "missing_input")


def _verification_layout():
    """verification/layout.py: where a job and its result are kept, by id (flat, or under the day it was submitted)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verification_layout", Path(__file__).resolve().parents[2] / "verification" / "layout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


layout = _verification_layout()


class Blocked(Exception):
    """The promotion cannot go on, and why. `main` is where it was."""


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def promotions(s) -> Path:
    return s.STATE / "promotions"


def state_path(s, base: str, frozen: str) -> Path:
    return promotions(s) / f"{base[:12]}-{frozen[:12]}.json"


def save(s, path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    s.atomic_write(path, json.dumps(state, indent=1) + "\n")


def tree_of(s, commit: str) -> str:
    return git(s, "rev-parse", f"{commit}^{{tree}}").stdout.decode().strip()


def is_record(path: str) -> bool:
    return any(path.startswith(r) if r.endswith("/") else path == r for r in RECORDS)


def is_generated(path: str) -> bool:
    return any(path.startswith(r) if r.endswith("/") else path == r for r in GENERATED) or bool(EXAMPLE_RECORDS.match(path))


# --------------------------------------------------------------------------- the frozen set

def frozen(s, base: str, head: str) -> list[dict]:
    """The commits of `ancestors(head) - ancestors(base)`, newest first, each with its trailers, the jobs whose
    results it added, and what it changed apart from generated records."""
    r = git(s, "log", "--format=%x01%H%x00%P%x00%B%x00", "--numstat", "--no-renames", head, "--not", base, timeout=600)
    if r.returncode:
        raise RuntimeError(f"git log: {r.stderr.decode(errors='replace').strip()[:300]}")
    changes = dict(line.split("\t") for line in jq(s, "log", "--no-graph", "-r", f"{base}..{head}", "-T",
                                                    'commit_id ++ "\\t" ++ change_id ++ "\\n"').stdout.splitlines())
    out = []
    for entry in r.stdout.decode(errors="replace").split("\x01")[1:]:
        sha, parents, message, stat = entry.split("\0", 3)
        files = added = deleted = records = 0
        jobs = set()
        for line in stat.strip().splitlines():
            a, d, path = line.split("\t", 2)
            if (found := layout.result_id_of(path)) and found[1] == "result.json":
                jobs.add(found[0])
            if is_generated(path):
                records += 1
                continue
            files += 1
            added += int(a) if a.isdigit() else 0
            deleted += int(d) if d.isdigit() else 0
        out.append({"commit": sha, "change": changes.get(sha, ""), "summary": message.strip().split("\n", 1)[0],
                    "merge": len(parents.split()) > 1, "files": files, "added": added, "deleted": deleted, "records": records,
                    "jobs": sorted(jobs), "trailers": [[sid, sha256] for sid, sha256 in s.TRAILER_RE.findall(message) if sha256]})
    return out


def trace_plan(s, commits: list[dict], manifests: dict[str, dict], stored) -> dict:
    """Where each log a frozen commit points at stands: public, withdrawn, to upload (stored in a workspace), or
    missing: no manifest lists it, or no workspace stores it. `stored(sid, sha)` says whether its bytes are at hand."""
    plan = {"public": [], "withdrawn": [], "upload": [], "missing": []}
    seen = set()
    for c in commits:
        for sid, sha in c["trailers"]:
            if (sid, sha) in seen:
                continue
            seen.add((sid, sha))
            name = f"{sid}/{sha[:12]}"
            info = ((manifests.get(sid) or {}).get("logs") or {}).get(sha)
            if info is None:
                plan["missing"].append(f"{name}: commit {c['commit'][:12]} points at it, and " + (
                    "its session's manifest in this tree does not list it" if sid in manifests else "this tree has no manifest of its session")
                    + " (the workspace that ran the session holds a newer one: land it, checkpoint, and promote that commit)")
            elif info.get("withdrawn"):
                plan["withdrawn"].append(name)
            elif info.get("url"):
                plan["public"].append(name)
            elif stored(sid, sha):
                plan["upload"].append(name)
            else:
                plan["missing"].append(f"{name}: commit {c['commit'][:12]} points at it, it is not uploaded, and no workspace of "
                                       "this machine stores it")
    return plan


def manifests_at(s, rev: str, sessions) -> dict[str, dict]:
    files = s.tree_files([(rev, f"llm-dlc/traces/{sid}/manifest.json") for sid in sessions])
    out = {}
    for (_, path), raw in files.items():
        if raw is not None:
            out[path.split("/")[2]] = json.loads(raw)
    return out


def stored_anywhere(s):
    roots = [s.REPO, *s.workspace_roots()]
    return lambda sid, sha: any((root / s.log_path(sid, sha).relative_to(s.REPO)).exists() for root in roots)


def originals(s, commits: list[dict], rev: str, settle: bool = False) -> dict:
    """What the private archive holds of the frozen set: the occurrences of its jobs, its sessions and its commits,
    by kind and state; those not yet verified off this machine; and the jobs it has nothing of (a gap: collected
    before capture began, or on a machine whose archive this one cannot see). With `settle`, one upload pass is
    made first for what is still pending."""
    jobs = sorted({j for c in commits for j in c["jobs"]})
    sessions = {sid for c in commits for sid, _ in c["trailers"]}
    shas = {c["commit"] for c in commits}
    out = {"jobs": len(jobs), "by_kind": {}, "occurrences": [], "unverified": [], "gaps": []}
    try:
        import artifacts
        if artifacts.off() or not (artifacts.home() / "journal.sqlite").exists():
            out["note"] = "this machine has no private archive journal"
            return out
        archive = artifacts.Archive()
    except Exception as e:
        out["note"] = f"the private archive could not be read: {type(e).__name__}"
        return out
    try:
        wanted = set(jobs)
        relevant = lambda r: not str(r.get("kind")).startswith("promotion-") and (  # a promotion's own records are not its evidence
            r.get("job") in wanted or r.get("session") in sessions or (r.get("source") or {}).get("commit") in shas)
        rows = [r for r in archive.rows() if relevant(r)]
        if settle and any(r["custody"]["state"] not in VERIFIED for r in rows):
            archive.retry_now()
            for _ in range(5):
                done = archive.upload()
                if done["errors"] or not (done["objects"] or done["receipts"] or done["intents"]):
                    break
            rows = [r for r in archive.rows() if relevant(r)]
    finally:
        archive.close()
    known = {r["id"]: r for r in rows}
    held = {r.get("job") for r in rows}
    results = s.tree_files([(rev, f"{layout.result_rel(j, how)}/result.json") for j in jobs for how in ("flat", "shards")]) if jobs else {}
    reader = None
    for job in jobs:
        raw = next((r for how in ("flat", "shards") if (r := results.get((rev, f"{layout.result_rel(job, how)}/result.json")))), None)
        try:
            named = ((json.loads(raw) if raw else {}).get("originals") or {}).get("occurrences") or []
        except ValueError:
            named = []
        named = list(named.values()) if isinstance(named, dict) else list(named)
        for occurrence in (o for o in named if isinstance(o, str) and o not in known):
            try:  # sealed by another machine: its receipt in the store says whether it is verified
                reader = reader or artifacts.Reader()
                known[occurrence] = reader.receipt(occurrence)
                held.add(job)
            except Exception as e:
                out["unverified"].append(f"{occurrence} (named by the result of job {job}): {str(e)[:160]}")
        if job not in held and not named:
            out["gaps"].append(job)
    for r in sorted(known.values(), key=lambda r: r["id"]):
        state = (r.get("custody") or {}).get("state") or "unknown"
        kinds = out["by_kind"].setdefault(r.get("kind") or "unknown", {})
        kinds[state] = kinds.get(state, 0) + 1
        out["occurrences"].append({"id": r["id"], "kind": r.get("kind"), "job": r.get("job"), "session": r.get("session"),
                                   "state": state, "access": r.get("access"), "bytes": (r.get("raw") or {}).get("bytes")})
        if state not in VERIFIED:
            out["unverified"].append(f"{r['id']} ({r.get('kind')}, {state})")
    return out


def covering(s, tree: str) -> dict | None:
    """The latest passed default run whose tree covers `tree` (the same, or differing only in files no test reads)."""
    sys.path.append(str(s.REPO / "lib" / "tools"))
    import default_run
    for record in reversed(default_run.records()):
        if default_run.covers(record["tree"], tree, s.REPO):
            return record
    return None


# --------------------------------------------------------------------------- the review view

def review(s, state: dict, commits: list[dict], plan: dict, orig: dict, develop: str) -> str:
    """One view of a promotion for whoever reviews it: the source diff by finished change first, then the test
    receipt, open decisions and evidence counts, and where to drill down. Generated records are counted, not listed."""
    base, head = state["base"], state["frozen"]
    later = len(git(s, "rev-list", develop, "--not", head).stdout.split()) if develop != head and have(s, develop) else 0
    lines = [f"# Promotion {state['id']}", "",
             f"`{REMOTE}/{MAIN}` {base[:12]} -> `{DEVELOP}` commit {head[:12]}: {len(commits)} commit(s), frozen. "
             + (f"`{DEVELOP}` is {later} commit(s) further on; they wait for the next promotion." if later else f"`{DEVELOP}` is at this commit."),
             "", "## Source changes, by finished change", ""]
    source = [c for c in commits if c["files"]]
    for c in source[:200]:
        lines.append(f"- `{c['change'][:12] or c['commit'][:12]}` {c['summary']}  (+{c['added']} -{c['deleted']} in {c['files']} file(s)"
                     + (f"; {len(c['jobs'])} job result(s)" if c["jobs"] else "") + ")")
    if len(source) > 200:
        lines.append(f"- ... and {len(source) - 200} more, in the inventory")
    only_records = sum(1 for c in commits if not c["files"] and not c["merge"])
    merges = sum(1 for c in commits if c["merge"])
    exclude = [f":(exclude){p.rstrip('/')}" for p in GENERATED if p != "llm-dlc/README.md"] + [":(exclude,glob)examples/*/records/**"]
    total = git(s, "diff", "--shortstat", base, head, "--", ".", *exclude).stdout.decode().strip()
    lines += ["", f"Together: {total or 'no source file changed'}. {only_records} commit(s) change generated records only "
              f"(traces, job specifications and results, examples' replay records); {merges} merge(s).",
              f"The whole diff: `git diff {base[:12]} {head[:12]} -- . {' '.join(repr(e) for e in exclude[:2])} ...`; one change: `jj show CHANGE`.",
              "", "## Default test run", ""]
    record = covering(s, tree_of(s, head))
    lines.append(f"A passed run covers this tree: tree {record['tree'][:12]}, {record['when']} ({record['tally']})." if record else
                 "No passed run covers this tree yet: the promotion runs the default run in the candidate workspace "
                 "(several minutes, a few GB), and `main` stays where it is unless it passes.")
    decisions = s.decision_problems(head)
    try:
        proposals = sum(1 for e in s.load_allowlist().values() if e.get("status") == "proposed")
    except Exception:
        proposals = 0
    lines += ["", "## Decisions", "",
              f"{len(decisions)} redaction decision(s) nobody is recorded as having taken" + (": " + "; ".join(decisions[:5]) if decisions else "")
              + f". {proposals} allow-list proposal(s) open in this checkout (a warning, not a blocker).",
              "", "## Evidence", "",
              f"Trace logs the frozen commits point at: {len(plan['public'])} public, {len(plan['withdrawn'])} withdrawn, "
              f"{len(plan['upload'])} to upload, {len(plan['missing'])} missing."]
    lines += [f"- MISSING {m}" for m in plan["missing"][:50]]
    if orig.get("note"):
        lines.append(f"Originals: {orig['note']}.")
    else:
        counts = "; ".join(f"{kind} " + ", ".join(f"{n} {state}" for state, n in sorted(states.items()))
                           for kind, states in sorted(orig["by_kind"].items())) or "none recorded"
        lines.append(f"Originals in the private archive, for {orig['jobs']} job(s) and the frozen sessions: {counts}.")
        lines += [f"- NOT VERIFIED {u}" for u in orig["unverified"][:50]]
        if orig["gaps"]:
            lines.append(f"{len(orig['gaps'])} job(s) have no original in the archive (collected before capture began, or elsewhere): "
                         + ", ".join(orig["gaps"][:8]) + (" ..." if len(orig["gaps"]) > 8 else "") + ". They are disclosed as gaps.")
    lines += ["", "Drill down: `python3 llm-dlc/tools/artifacts.py list --job ID` (or `--session`, `--source COMMIT`), "
              "`show ID`, `fetch ID --to DIR`.", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- the command, where it is asked

def usage() -> int:
    print("usage: sync.py promote --rev REV [--dry-run]", file=sys.stderr)
    return 2


def cmd_promote(s, args: list[str]) -> int:
    args, skipped = s.without_skip_tests(args)
    for i, a in enumerate(args):
        revision = i > 0 and args[i - 1] == "--rev"
        if a.split("=", 1)[0] in checkpoint.REFUSED_ARGS or "*" in a or (":" in a and not revision and not a.startswith("--")):
            print(f"sync.py promote: {a!r} is not for this command. It moves {REMOTE}'s {MAIN} forward to one revision of "
                  f"{DEVELOP}: no other ref or remote, no pattern, no force", file=sys.stderr)
            return 2
    if args[:1] == ["--inside"] and len(args) == 2:
        return inside(s, Path(args[1]), skipped)
    real = s.jj  # where the command is asked, no working copy is read: the candidate has one of its own
    s.jj = lambda *a: real(*a) if "--ignore-working-copy" in a else real("--ignore-working-copy", *a)
    try:
        return _promote(s, args, skipped)
    finally:
        s.jj = real


def _promote(s, args: list[str], skipped: str | None) -> int:
    dry = "--dry-run" in args
    rest = [a for a in args if a != "--dry-run"]
    if len(rest) != 2 or rest[0] != "--rev":
        return usage()
    try:
        target = checkpoint.resolve(s, rest[1])
        main, develop = remote_ref(s, MAIN), remote_ref(s, DEVELOP)
    except (ValueError, RuntimeError) as e:
        print(f"not promoted: {e}", file=sys.stderr)
        return 1
    head = target["commit"]

    def no(why: str) -> int:
        print(f"not promoted: {why}", file=sys.stderr)
        return 1
    if main is None:
        return no(f"{REMOTE} has no {MAIN}")
    if develop is None:
        return no(f"{REMOTE} has no {DEVELOP} yet: a promotion takes a commit that is on it. Create it with `sync.py checkpoint --bootstrap`")
    if target["conflict"]:
        return no(f"{head[:12]} holds an unresolved conflict")
    if not have(s, main) or not have(s, develop):
        return no(f"{REMOTE}'s {MAIN} or {DEVELOP} is at a commit this repository does not have: fetch first (`jj git fetch --remote {REMOTE}`)")
    if main == head or is_ancestor(s, head, main):
        earlier = next((p for p in sorted(promotions(s).glob("*.json")) if (d := _read(p)) and d.get("frozen") == head
                        and d.get("candidate") == main and d.get("stage") != "promoted"), None)
        if earlier is None or dry:
            print(f"nothing to promote: {REMOTE}/{MAIN} ({main[:12]}) already holds {head[:12]}")
            return 0
        path, state = earlier, _read(earlier)  # the push went out and the record did not: finish that promotion
    else:
        if head != develop and not is_ancestor(s, head, develop):
            return no(f"{head[:12]} is not on {REMOTE}'s {DEVELOP} ({develop[:12]}): checkpoint it first (`sync.py checkpoint --rev ...`). "
                      "A promotion takes code others could already read")
        if not is_ancestor(s, main, head):
            return no(f"{REMOTE}'s {MAIN} ({main[:12]}) is not an ancestor of {head[:12]}: another promotion moved it. Take it into "
                      f"the line with an ordinary merge, checkpoint the merge, and promote that. {MAIN} is never forced")
        path = state_path(s, main, head)
        state = _read(path) or {"schema": SCHEMA, "id": f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{head[:12]}", "base": main,
                                "frozen": head, "stage": "frozen", "started": utc()}
    try:
        commits = frozen(s, state["base"], head)
        plan = trace_plan(s, commits, manifests_at(s, head, {sid for c in commits for sid, _ in c["trailers"]}), stored_anywhere(s))
        orig = originals(s, commits, head)
        view = review(s, state, commits, plan, orig, develop)
    except RuntimeError as e:
        return no(str(e))
    print(view)
    if dry:
        blockers = len(plan["missing"]) + len(orig["unverified"])
        print(f"dry run: nothing was built, uploaded or pushed. {blockers} thing(s) above would block the candidate"
              + (" until the private archive verifies them or they are found" if blockers else "") + ".")
        return 0
    folder = promotions(s) / state["id"]
    folder.mkdir(parents=True, exist_ok=True)
    s.atomic_write(folder / "review.md", view)
    save(s, path, state)
    try:
        candidate = candidate_workspace(s, head)
    except Blocked as e:
        return no(str(e))
    return run_inside(s, candidate, path, skipped)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def candidate_root(s) -> Path:
    if os.environ.get("ITL_PROMOTE_WORKSPACE"):
        return Path(os.environ["ITL_PROMOTE_WORKSPACE"])
    r = jq(s, "workspace", "root", "--name", "default")
    base = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else s.REPO
    return base.with_name(base.name + "-promote")


def candidate_workspace(s, head: str) -> Path:
    """The folder of the jj workspace promotions are built in, made on the first promotion and kept: removing a
    workspace is the user's. It holds no one's work, only what a promotion generates."""
    names = jq(s, "workspace", "list", "-T", 'name ++ "\\n"').stdout.split()
    if WORKSPACE in names:
        r = jq(s, "workspace", "root", "--name", WORKSPACE)
        if r.returncode or not Path(r.stdout.strip()).is_dir():
            raise Blocked(f"the jj workspace `{WORKSPACE}` is listed and its folder is gone: `jj workspace forget {WORKSPACE}` is the user's, then promote again")
        return Path(r.stdout.strip())
    root = candidate_root(s)
    if root.exists() and any(root.iterdir()):
        raise Blocked(f"{root} exists and is not the `{WORKSPACE}` workspace: the candidate is not built over someone's folder")
    print(f"making the candidate workspace {root} (once; later promotions move it)", flush=True)
    # jj makes a workspace only with the asking one's working copy in view: this once it is snapshotted, as any jj
    # command does (no file changes). Every later promotion reads no working copy but the candidate's.
    r = subprocess.run([s.JJ, "--quiet", "--config", "snapshot.max-new-file-size=100MiB", "workspace", "add", "--name", WORKSPACE,
                        "-r", head, str(root)], cwd=s.REPO, capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise Blocked(f"jj workspace add failed: {r.stderr.strip()[:300]}")
    return root


def run_inside(s, candidate: Path, path: Path, skipped: str | None) -> int:
    """The rest of the promotion, run by the candidate checkout's own sync.py: its files, its tools, its tests."""
    tool = candidate / "llm-dlc" / "tools" / "sync.py"
    if not (tool.parent / "promote.py").exists():
        print(f"not promoted: the revision's own tools have no `promote` ({tool.parent}): it predates this command", file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(tool), "promote", "--inside", str(path),
                           *(["--skip-tests", skipped] if skipped is not None else [])], cwd=candidate).returncode


# --------------------------------------------------------------------------- in the candidate workspace

def inside(s, path: Path, skipped: str | None) -> int:
    state = _read(path)
    if not state:
        print(f"not promoted: no promotion is recorded at {path}", file=sys.stderr)
        return 1
    started = time.perf_counter()
    try:
        with s.Operation("promote", exclusive=True):
            _inside(s, path, state, skipped)
    except Blocked as e:
        state["last_failure"] = {"at": utc(), "stage": state.get("stage"), "reason": str(e)}
        save(s, path, state)
        where = remote_ref(s, MAIN)
        print(f"not promoted: {e}\n{REMOTE}/{MAIN} is at {(where or 'nothing')[:12]}. The promotion {state['id']} is kept as it stands "
              f"({path}); the same command continues it", file=sys.stderr)
        return 1
    print(f"promotion {state['id']} finished in {time.perf_counter() - started:.0f} s")
    return 0


def _inside(s, path: Path, state: dict, skipped: str | None) -> None:
    base, head = state["base"], state["frozen"]
    timing = state.setdefault("timing_seconds", {})

    def step(name: str, fn):
        t = time.perf_counter()
        try:
            return fn()
        finally:
            timing[name] = round(timing.get(name, 0) + time.perf_counter() - t, 2)
            save(s, path, state)
    main = remote_ref(s, MAIN)
    if main != state.get("candidate"):
        if main != base:
            raise Blocked(f"{REMOTE}'s {MAIN} moved from {base[:12]} to {(main or 'nothing')[:12]} since this promotion froze its set: "
                          "take it into the line with an ordinary merge, checkpoint the merge, and promote that")
        candidate = state.get("candidate")
        if not (candidate and have(s, candidate) and git(s, "rev-parse", f"{candidate}^@").stdout.decode().split() == [head]):
            step("build", lambda: build(s, path, state))
        candidate = state["candidate"]
        step("scan", lambda: scan_candidate(s, state))
        step("gate", lambda: gate_candidate(s, state, skipped))
        done, how = step("push", lambda: checkpoint.push(s, candidate, MAIN, base))
        if not done:
            raise Blocked(how)
        state["main"] = {"before": base, "after": candidate, "pushed": how, "at": utc()}
        state["stage"] = "pushed"
        save(s, path, state)
    s.jj("git", "import")
    checkpoint.ensure_immutable(s)
    if "develop" not in state:
        state["develop"] = step("develop", lambda: forward(s, state))
    state["main"]["observed"] = remote_ref(s, MAIN)
    state["stage"], state["finished"] = "promoted", utc()
    state.pop("last_failure", None)
    save(s, path, state)
    receipt = promotions(s) / state["id"] / "receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    s.atomic_write(receipt, json.dumps(state, indent=1) + "\n")
    seal(s, receipt, "promotion-receipt", f"promotions/{state['id']}/receipt.json", state, wait=False)
    d = state["develop"]
    print(f"promoted: {REMOTE}/{MAIN} {base[:12]} -> {state['candidate'][:12]} ({state['commits']} commit(s) of {DEVELOP} up to "
          f"{head[:12]}, tree {state['tree'][:12]})")
    print(f"  {DEVELOP}: {d['how']}")
    print(f"  receipt: {receipt}")


def prepare(s, head: str) -> None:
    """Put the candidate's working copy on the frozen commit. What an interrupted promotion left there is generated,
    and is made again; anything else is not this command's to touch."""
    r = s.jj("status")
    if "stale" in (r.stderr or ""):
        subprocess.run([sys.executable, str(s.REPO / "llm-dlc" / "tools" / "unstale.py")], cwd=s.REPO, capture_output=True, timeout=600)
    changed = s.jj("diff", "--name-only").stdout.splitlines()
    if foreign := [p for p in changed if not is_record(p)]:
        raise Blocked(f"the candidate workspace {s.REPO} holds changes no promotion makes ({', '.join(foreign[:5])}): it is for "
                      "promotions only, and they are left as they are")
    at = s.jj_commits("@")[0]
    parent = s.jj("log", "--no-graph", "-r", "@-", "-T", 'commit_id ++ "\\n"').stdout.split()
    if parent == [head] and not at["description"].strip():
        return
    if s.jj("new", head).returncode:
        raise Blocked(f"the candidate workspace could not be moved to {head[:12]}")
    if changed and not at["description"].strip():
        s.jj("abandon", at["change_id"])  # generated files of an interrupted promotion of another commit


def build(s, path: Path, state: dict) -> None:
    """The publication record of the frozen set, as a commit of its own on the frozen commit."""
    base, head, ident = state["base"], state["frozen"], state["id"]
    prepare(s, head)
    if attempt := state.pop("attempt", None):  # a record an earlier try committed and then found wanting: made again
        s.jj("abandon", attempt)
    commits = frozen(s, base, head)
    for line in s.adopt_logs():
        print(f"took {line}")
    manifests = s.all_manifests()
    plan = trace_plan(s, commits, manifests, lambda sid, sha: s.log_path(sid, sha).exists())
    if plan["missing"]:
        raise Blocked("the receipt of " + str(len(plan["missing"])) + " log(s) of the frozen commits is missing:\n  "
                      + "\n  ".join(plan["missing"][:50]))
    orig = originals(s, commits, head, settle=True)
    if orig["unverified"]:
        raise Blocked(f"{len(orig['unverified'])} original(s) of the frozen set are not verified in the private archive (run "
                      "`python3 llm-dlc/tools/artifacts.py status`, and `upload --drain` once the store answers):\n  "
                      + "\n  ".join(orig["unverified"][:50]))
    # The frozen commits wrote their sessions' manifests alone: the summaries, the metrics and the overview are
    # rendered here, once, from the logs just taken (sync.py, RENDERING), and checked as rendered.
    s.cmd_sync([])
    if s.cmd_check(["--rendered"]) != 0:  # before the upload: a log with a leak must not reach the CDN
        raise Blocked("the trace check failed in the candidate; nothing was uploaded")
    if s.cmd_upload(include_at=True) != 0:
        raise Blocked("a log could not be uploaded; what was verified is kept, and the same command goes on from there")
    manifests = s.all_manifests()
    plan = trace_plan(s, commits, manifests, lambda sid, sha: False)
    if plan["missing"] or plan["upload"]:
        raise Blocked("after the upload these logs of the frozen commits still have no public URL:\n  "
                      + "\n  ".join((plan["missing"] + plan["upload"])[:50]))
    folder = promotions(s) / ident
    folder.mkdir(parents=True, exist_ok=True)
    inventory = {"schema": INVENTORY_SCHEMA, "promotion": ident, "base": base, "frozen": head, "frozen_tree": tree_of(s, head),
                 "commits": [{k: c[k] for k in ("commit", "change", "summary", "merge", "files", "jobs", "trailers")} for c in commits],
                 "trace_logs": {k: sorted(v) for k, v in plan.items() if k in ("public", "withdrawn")},
                 "originals": {"occurrences": orig["occurrences"], "gaps": orig["gaps"], "note": orig.get("note")}}
    data = json.dumps(inventory, indent=1, sort_keys=True).encode() + b"\n"
    (folder / "inventory.json").write_bytes(data)
    occurrence = seal(s, folder / "inventory.json", "promotion-inventory", f"promotions/{ident}/inventory.json",
                      {**state, "candidate": None, "tree": inventory["frozen_tree"]}, wait=True)
    summary = {
        "schema": SUMMARY_SCHEMA, "kind": "promotion", "id": ident,
        "source": {"base": base, "frozen": head, "frozen_tree": inventory["frozen_tree"], "commits": len(commits),
                   "source_commits": sum(1 for c in commits if c["files"]), "jobs": orig["jobs"]},
        "evidence": {"availability": "verified",
                     "trace_logs": {"public": len(plan["public"]), "withdrawn": len(plan["withdrawn"])},
                     "originals": {"by_kind": orig["by_kind"], "gaps": len(orig["gaps"])}},
        "archive": {"occurrence": occurrence, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "read": f"python3 llm-dlc/tools/artifacts.py fetch {occurrence} --to DIR"},
        "disposition": "published",
        "policy": {"checkpoint": checkpoint.POLICY, "redaction": s.REDACTION_POLICY},
    }
    text = json.dumps(summary, indent=1, sort_keys=True) + "\n"
    if problems := summary_problems(summary, len(text.encode())):
        raise Blocked("the promotion's summary is not one that may be published: " + "; ".join(problems))
    rel = f"{ARTIFACTS}/{ident[:4]}/{ident[4:6]}/{ident[6:8]}/promotion-{ident}.json"
    (s.REPO / rel).parent.mkdir(parents=True, exist_ok=True)
    s.atomic_write(s.REPO / rel, text)
    s.write_index()  # the overview counts uploads
    message = (f"Record promotion {ident}: {len(commits)} commit(s) of {DEVELOP} and their evidence\n\n"
               f"The publication record of a promotion of {REMOTE}/{MAIN} from {base[:12]} to {DEVELOP}'s {head[:12]}: {len(commits)} "
               f"commit(s), frozen when the promotion began (what landed on {DEVELOP} later is not part of it). It records the "
               f"URLs of the trace logs those commits point at ({len(plan['public'])} public, {len(plan['withdrawn'])} withdrawn), "
               f"the regenerated session index and overview, and {rel}, a summary naming the private inventory of everything the "
               f"promotion covers (occurrence {occurrence}). No source file changes here: the diff from {head[:12]} is generated "
               "records only, and the default run's receipt for this tree is kept outside it.")
    if s.jj("commit", "-m", message).returncode:
        raise Blocked("jj commit failed in the candidate workspace")
    candidate = s.jj("log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()
    state["attempt"] = candidate
    save(s, path, state)
    changed = git(s, "diff", "--name-only", "--no-renames", head, candidate).stdout.decode().splitlines()
    if strays := [p for p in changed if not is_record(p)]:
        raise Blocked(f"the publication record {candidate[:12]} changes files that are not generated records: {', '.join(strays[:5])}")
    if s.cmd_check(["--rendered"]) != 0:
        raise Blocked("the trace check failed on the publication record")
    if problems := s.publication_gate(candidate):
        raise Blocked("the publication record is not what was checked:\n  " + "\n  ".join(problems[:20]))
    state.pop("attempt")
    state.update({"candidate": candidate, "tree": tree_of(s, candidate), "commits": len(commits), "summary": rel,
                  "inventory": {"occurrence": occurrence, "sha256": summary["archive"]["sha256"]},
                  "evidence": summary["evidence"], "stage": "built"})
    save(s, path, state)
    print(f"built the publication record {candidate[:12]} on {head[:12]}: {len(changed)} generated file(s)")


def summary_problems(doc: dict, size: int) -> list[str]:
    """What keeps a summary out of git: the common fields every kind carries (llm-dlc/publication-summary.schema.json),
    its size, and what it must never hold: a credential's field, a signed or expiring URL."""
    problems = [f"no `{k}`" for k in ("schema", "kind", "id", "source", "evidence", "archive", "disposition", "policy") if k not in doc]
    if doc.get("schema") != SUMMARY_SCHEMA:
        problems.append(f"schema is not {SUMMARY_SCHEMA}")
    if doc.get("disposition") not in ("published", "withheld", "private-only"):
        problems.append("disposition is not one of published, withheld, private-only")
    if size > SUMMARY_MAX:
        problems.append(f"{size:,} bytes, over the {SUMMARY_MAX:,} a summary may be: the detail belongs in the private inventory")
    text = json.dumps(doc).lower()
    for needle in ("x-amz-signature", "x-amz-credential", "secret_access_key", "access_key_id", "authorization"):
        if needle in text:
            problems.append(f"holds `{needle}`")
    return problems


def seal(s, file: Path, kind: str, logical: str, state: dict, wait: bool) -> str:
    """Seal one of the promotion's own records in the private archive, as an ordinary occurrence, and return its id.
    With `wait`, it must be verified in the store before this returns: what `main` is about to depend on is not left
    on this machine only."""
    try:
        import artifacts
        if artifacts.off():
            raise Blocked("the private archive is switched off (ITL_ORIGINALS_OFF): a promotion seals its records there")
        archive = artifacts.Archive()
    except Blocked:
        if wait:
            raise
        return ""
    except Exception as e:
        if wait:
            raise Blocked(f"the private archive could not be opened: {type(e).__name__}: {e}")
        return ""
    try:
        record = archive.capture(file, kind, logical, run=state["id"], source={
            "commit": state.get("candidate") or state["frozen"], "tree": state.get("tree"), "base": state["base"], "frozen": state["frozen"]})
        if not wait:
            artifacts.kick()
            return record["id"]
        archive.retry_now()
        for _ in range(5):
            if archive.releasable(record["id"]):
                return record["id"]
            done = archive.upload()
            if done["errors"]:
                break
        if archive.releasable(record["id"]):
            return record["id"]
        raise Blocked(f"{file.name} is sealed here ({record['id']}) and is not verified in the private archive"
                      + (f": {done['errors'][0][:200]}" if done["errors"] else "") + ". `main` does not move on a record that is on this machine only")
    finally:
        archive.close()


def scan_candidate(s, state: dict) -> None:
    """The bytes the push adds to what `develop` already published, read as a checkpoint reads them."""
    candidate, bases = state["candidate"], [state["frozen"], state["base"]]
    commits, blobs = checkpoint.outgoing(s, candidate, bases)
    problems, stats = checkpoint.scan(s, s.Redactor(), commits, blobs, candidate, bases)
    problems += s.decision_problems(candidate)
    if problems:
        raise Blocked(f"{len(problems)} problem(s) in what the push would add:\n  " + "\n  ".join(problems[:50]))
    state["scan"] = stats


def run_default(s, log: Path) -> int:
    """The default run, in the candidate, in a memory cap of its own; its output goes to the terminal and to `log`."""
    argv = [sys.executable, str(s.REPO / "lib" / "tools" / "test_costs.py"), "run", "--rust-jobs", "2"]
    if shutil.which("systemd-run"):
        argv = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=8G", "-p", "MemorySwapMax=0", *argv]
    with open(log, "wb") as out:
        proc = subprocess.Popen(argv, cwd=s.REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in proc.stdout:
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            out.write(line)
        return proc.wait()


def gate_candidate(s, state: dict, skipped: str | None) -> None:
    """A passed default run must cover the candidate's tree: one already recorded, or one run here. The gate's
    record, and the run's log when it ran, are sealed and verified in the archive before `main` may move."""
    tree, folder = state["tree"], promotions(s) / state["id"] / "gate"
    folder.mkdir(parents=True, exist_ok=True)
    record, ran, exit_code = covering(s, tree), False, None
    if record is None and skipped is None:
        print(f"no passed default run covers tree {tree[:12]}: running it in the candidate workspace", flush=True)
        ran, exit_code = True, run_default(s, folder / "default-run.log")
        record = covering(s, tree)
    passed = record is not None or skipped is not None
    doc = {"schema": GATE_SCHEMA, "promotion": state["id"], "commit": state["candidate"], "tree": tree, "passed": passed,
           "covering_run": record, "ran_here": ran, "exit": exit_code, "skipped": skipped, "at": utc()}
    s.atomic_write(folder / "gate.json", json.dumps(doc, indent=1) + "\n")
    state["gate"] = doc
    try:
        doc["occurrence"] = seal(s, folder, "promotion-gate", f"promotions/{state['id']}/gate", state, wait=passed)
    finally:
        state["stage"] = "gate passed" if passed else "gate failed"
    if not passed:
        raise Blocked(f"the default run did not pass for the candidate's tree {tree[:12]} (exit {exit_code}; its log is "
                      f"{folder / 'default-run.log'}). A default run that fails is taken up before new work")
    if skipped is not None and record is None:
        print(f"promoting without a passed default run, as asked: {skipped}", file=sys.stderr)
    else:
        print(f"the default run covers tree {tree[:12]}: tree {record['tree'][:12]}, {record['when']} ({record['tally']})")


def forward(s, state: dict) -> dict:
    """Bring `develop` up to the publication record: forward when it is still at the frozen commit, and by an
    ordinary merge when it moved meanwhile, so the later work is kept and the next promotion starts from `main`."""
    head, candidate = state["frozen"], state["candidate"]
    develop = remote_ref(s, DEVELOP)
    if develop == candidate or (develop and have(s, develop) and is_ancestor(s, candidate, develop)):
        return {"before": develop, "after": develop, "how": f"already holds the record ({develop[:12]})"}
    if develop == head:
        done, how = checkpoint.push(s, candidate, DEVELOP, head)
        s.jj("git", "import")
        return {"before": head, "after": candidate if done else head, "pending": not done,
                "how": f"moved forward to the record {candidate[:12]}" if done else f"NOT moved ({how}): checkpoint {candidate[:12]} by hand"}
    if not develop or not have(s, develop):
        s.jj("git", "fetch", "--remote", REMOTE)
    by_hand = (f"NOT merged: in a workspace on {DEVELOP}, `jj new {DEVELOP}@{REMOTE} {candidate[:12]}`, `sync.py regenerate`, "
               "commit, and checkpoint the merge")
    if not develop or not have(s, develop):
        return {"before": develop, "after": develop, "pending": True, "how": by_hand}
    message = (f"Merge the record of promotion {state['id']} into {DEVELOP}\n\n{DEVELOP} went on while the promotion ran: this takes "
               f"the publication record {candidate[:12]} (now {REMOTE}/{MAIN}) into it, so the next promotion starts from {MAIN}.")
    if s.jj("new", develop, candidate, "-m", message).returncode or s.cmd_regenerate([]) != 0 or s.jj("new").returncode:
        return {"before": develop, "after": develop, "pending": True, "how": by_hand}
    merge = s.jj("log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout.strip()
    status = checkpoint.cmd_checkpoint(s, ["--rev", merge])
    return {"before": develop, "after": merge if status == 0 else develop, "merge": merge, "pending": status != 0,
            "how": f"moved on to {develop[:12]} meanwhile; merged the record into it as {merge[:12]}" if status == 0
            else f"merged as {merge[:12]} here, and the checkpoint of the merge was refused: see above"}
