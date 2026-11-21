"""Order private candidates and check the evidence in a replay packet before admission."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def rank(seed, stable_id):
    return hashlib.sha256(seed + stable_id.encode("utf-8")).digest()


def private_path(path):
    path = path.resolve()
    require(
        not any((p / "llm-dlc/tools/sync.py").is_file() for p in (path, *path.parents)),
        "use a private workspace outside the checkout",
    )
    return path


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "UTC offset required")
    return parsed.astimezone(timezone.utc)


def order(args):
    seed = private_path(args.seed).read_bytes()
    committed = json.loads(args.commitment.read_bytes())["seed_sha256"]
    require(len(seed) == 32 and hashlib.sha256(seed).hexdigest() == committed, "seed mismatch")
    rows = json.loads(private_path(args.candidates).read_bytes())
    ids = [row["stable_id"] for row in rows]
    require(len(ids) == len(set(ids)), "duplicate stable ID")
    if args.anchor is None:
        source_order = {"compsuite": 0, "bump": 1}

        def sort_key(row):
            identifier = row["stable_id"]
            require(re.fullmatch(r"compsuite:i-[0-9]+|bump:[a-f0-9]{40}", identifier), "invalid source ID")
            return source_order[identifier.split(":", 1)[0]], rank(seed, identifier)
    else:
        anchor = utc(args.anchor)
        cutoff = utc(args.cutoff)

        def sort_key(row):
            tier = row["match_tier"]
            require(type(tier) is int and tier in (1, 2, 3), "invalid routine matching tier")
            require(re.fullmatch(r"github:[a-z0-9_.-]+/[a-z0-9_.-]+#[1-9][0-9]*", row["stable_id"]),
                    "expected a normalized PR ID")
            merged = utc(row["merged_at"])
            require(merged <= cutoff, "PR merged after cutoff")
            distance = abs(merged - anchor)
            require(distance.total_seconds() <= 365 * 86400, "date outside matching window")
            return tier, distance, rank(seed, row["stable_id"])

    rows.sort(key=sort_key)
    destination = private_path(args.output)
    with tempfile.NamedTemporaryFile(dir=destination.parent) as staged:
        staged.write(json.dumps(rows, ensure_ascii=False, indent=2).encode() + b"\n")
        staged.flush()
        os.fsync(staged.fileno())
        os.link(staged.name, destination)
    print(json.dumps({"ordered_candidates": len(rows)}))


def evidence(root, name):
    require(isinstance(name, str) and bool(name), "missing evidence path")
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(), "missing packet evidence")
    require(path.stat().st_size > 0, "empty packet evidence")
    return path


def json_evidence(root, name):
    return json.loads(evidence(root, name).read_bytes())


def check_test(root, result):
    """Count the exact testcase, including explicitly identified parameterized names."""
    if result["format"] == "custom":
        evidence(root, result["execution_record"])
        require(result["outcome"] in ("pass", "failure", "error"), "test did not execute")
        return result["outcome"]
    require(result["format"] == "junit-xml", "unrecognized named-test evidence")
    paths = [evidence(root, name) for name in result["reports"]]
    require(len(paths) == len(set(paths)), "duplicate report path")
    matches = []
    for path in paths:
        for case in ET.parse(path).iter():
            if case.tag.split("}")[-1] == "testcase" and (
                case.get("classname"), case.get("name")
            ) == (result["class"], result["name"]):
                matches.append(case)
    require(len(matches) == 1, "named test missing or ambiguous")
    nodes = {child.tag.split("}")[-1] for child in matches[0]}
    status = matches[0].get("status", "").lower()
    require("skipped" not in nodes and status not in {"skipped", "notrun", "disabled"}, "named test skipped")
    for outcome in ("error", "failure"):
        if outcome in nodes:
            return outcome
    return "pass"


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))


def check_source(root, side):
    require(bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", side["revision"])), "invalid revision")
    source = json_evidence(root, side["production_manifest"])
    require(source["source"], "production source manifest is empty")
    for group in ("source", "generated"):
        mapping = source[group]
        require(isinstance(mapping, dict), "expected source-to-digest mapping")
        require(all(re.fullmatch(r"[0-9a-f]{64}", v) for v in mapping.values()), "invalid source hash")
    evidence(root, side["effective_pom"])
    evidence(root, side["subject_environment"])
    classpath = json_evidence(root, side["ordered_classpath"])
    require(isinstance(classpath, list) and bool(classpath), "empty ordered classpath")
    for artifact in classpath:
        require(
            nonempty_text(artifact["name"]) and re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]),
            "invalid classpath entry",
        )
    return source, classpath


def check_run(root, run, seen, entry, named_test, side, classpath):
    # The runtime observer writes this record in its own fresh working directory.
    path = evidence(root, run["receipt"])
    record = json.loads(path.read_bytes())
    run_id = record["run_id"]
    require(nonempty_text(run_id) and run_id not in seen, "reused run identity")
    seen.add(run_id)
    require(record["entry"] == entry and record["reached"] is True, "consumer operation not reached")
    evidence(root, run["execution_log"])
    loaded = json_evidence(root, run["loaded_artifacts"])
    available = {artifact["sha256"] for artifact in classpath}
    for artifact in loaded:
        require(nonempty_text(artifact["class"]) and artifact["sha256"] in available,
                "loaded artifact absent from resolved classpath")
    require({"consumer", "dependency"} <= {a["role"] for a in loaded}, "missing class origins")
    dependency = sorted({a["sha256"] for a in loaded if a["role"] == "dependency"})
    outcome = None
    if named_test:
        for field in ("class", "name"):
            require(run["test"][field] == named_test[field], "wrong developer testcase")
        outcome = check_test(root, run["test"])
        if side == "old":
            require(outcome == "pass", "developer testcase did not pass before upgrade")
    companion = ("companion" in record, canonical(record.get("companion")))
    return canonical(record["observation"]), companion, tuple(dependency), outcome


def audit(folder):
    root = private_path(folder)
    reference = json_evidence(root, "reference.json")
    require(reference["source_kind"] in ("upstream_pr", "benchmark_pair"), "unknown source kind")
    require(
        all(nonempty_text(reference[k]) for k in ("stable_id", "entry", "observer", "scope", "consequence")),
        "incomplete caller observation",
    )
    for key in ("closure_review", "independent_basis"):
        evidence(root, reference[key])
    review = json_evidence(root, reference["eligibility_review"])
    require(review["ordinary_functional_upgrade"] is True and review["production_java_maven"] is True
            and review["security_incident"] is False, "outside the declared eligibility")
    evidence(root, review["evidence"])
    basis = reference["basis_kind"]
    require(
        basis in ("developer_expectation", "independent_discriminator", "exhaustive_oracle",
                  "justified_contract", "independent_proof"),
        "unknown basis",
    )
    named_test = reference.get("named_test")
    if reference["stable_id"].startswith("compsuite:"):
        require(isinstance(named_test, dict), "CompSuite requires its developer testcase")
    if basis == "developer_expectation":
        require(isinstance(named_test, dict), "developer testcase unidentified")
    sources = {}
    classpaths = {}
    results = {}
    seen = set()
    workdirs = set()
    for side in ("old", "new"):
        subject = reference[side]
        sources[side], classpaths[side] = check_source(root, subject)
        runs = subject["runs"]
        min_runs = 2 if reference["stable_id"].startswith("compsuite:") else 1
        require(len(runs) >= min_runs, "missing independent replay")
        current = []
        for run in runs:
            rundir = evidence(root, run["receipt"]).parent
            require(rundir not in workdirs, "reused replay directory")
            workdirs.add(rundir)
            current.append(check_run(root, run, seen, reference["entry"], named_test, side, classpaths[side]))
        require(len(set(current)) == 1, "runtime outcomes did not reproduce")
        results[side] = current[0]
    require(reference["old"]["revision"] != reference["new"]["revision"], "same revision")
    require(sources["old"] == sources["new"], "production or generated source differs")
    require(classpaths["old"] != classpaths["new"], "identical resolved classpaths")
    before, old_companion, old_dependency, _ = results["old"]
    after, new_companion, new_dependency, _ = results["new"]
    require(old_dependency != new_dependency, "identical loaded upgrade artifacts")
    require(old_companion == new_companion, "companion differs")
    if before == after:
        require(basis in ("exhaustive_oracle", "justified_contract", "independent_proof"),
                "preservation lacks an independent basis")
        expected = json_evidence(root, reference["expected_observation"])
        require(before == canonical(expected), "runtime disagrees with independent expectation")
        return "preservation"
    if not old_companion[0]:
        require(nonempty_text(reference.get("companion_absence")), "explain absent preserving companion")
    return "change"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate = commands.add_parser("order", help="write the frozen order into a private file")
    candidate.add_argument("candidates", type=Path)
    candidate.add_argument("output", type=Path)
    candidate.add_argument("--commitment", required=True, type=Path)
    candidate.add_argument("--seed", required=True, type=Path)
    candidate.add_argument("--anchor", help="UTC time of a behavioral upgrade for routine matching")
    candidate.add_argument("--cutoff", default="2026-11-20T23:00:00Z", help="merged-PR search cutoff")
    review = commands.add_parser("audit", help="check one private reference packet before admission")
    review.add_argument("folder", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "order":
            order(args)
        else:
            audit(args.folder)
            print("Reference evidence checks passed.")
    except (OSError, ValueError, KeyError, IndexError, TypeError, ET.ParseError):
        # Identifiers, assertions and exception text from the private input stay off stdout.
        print("Curation checks failed. Inspect the packet within the curator environment.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
