"""Seal a first maintainer report and score original-scope PR decisions after independent adjudication."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from curation.seal_reference import SIGNATURE_CONTEXT


LABELS = ("Upgrade", "Caller-visible behavior", "Result", "Scope", "Review action")
ROUTES = {"native", "other-proof", "exhaustive-jvm", "jvm-witness", "open", "unavailable"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(record):
    return (json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(t.utcoffset() is not None, "timestamp has no timezone")
    return t


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value), "invalid case or build ID")
    return value


def hex_digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "missing SHA-256 identity")
    return value


def verified_document(path, key, purpose):
    envelope = json.loads(path.read_bytes())
    data = canonical(envelope["payload"])
    key.verify(bytes.fromhex(envelope["signatureHex"]), purpose.encode("ascii") + b"\0" + data)
    return envelope["payload"]


def evidence_file(root, item):
    name, expected = Path(item["file"]), hex_digest(item["sha256"])
    require(not name.is_absolute() and ".." not in name.parts, "evidence path leaves the packet")
    source = (root / name).resolve(strict=True)
    require(source.is_relative_to(root.resolve()) and source.is_file(), "evidence is outside the packet")
    with source.open("rb") as stream:
        require(hashlib.file_digest(stream, "sha256").hexdigest() == expected, f"evidence digest differs: {name}")
    return source


def check_operator(doc):
    identifier(doc["case_id"])
    identifier(doc["build"])
    for key in ("input_sha256", "product_sha256", "environment_sha256"):
        hex_digest(doc[key])
    require(doc["route"] in ROUTES, "unknown evidence route")
    require(isinstance(doc["evidence"], list), "missing evidence list")
    require(doc["route"] in {"open", "unavailable"} or doc["evidence"], "a verdict needs evidence")
    if doc["route"] != "unavailable":
        for name in ("primary_claim", "observer", "domain", "scope"):
            require(isinstance(doc[name], str) and doc[name].strip(), f"missing {name}")
        require(isinstance(doc["artifacts"], dict) and set(doc["artifacts"]) == {"old", "new"},
                "bind both ordered classpaths")
        for side in doc["artifacts"].values():
            require(isinstance(side, list) and side, "empty runtime classpath")
            for artifact in side:
                hex_digest(artifact)
    require(doc.get("first_blocker") or doc["route"] not in {"open", "unavailable"}, "unresolved case needs its blocker")
    start, end = timestamp(doc["intake_utc"]), timestamp(doc["finished_utc"])
    seconds = (end - start).total_seconds()
    require(seconds >= 0, "report precedes intake")
    useful = doc["first_actionable_utc"]
    if useful is not None:
        require(start <= timestamp(useful) <= end, "first actionable observation is outside the run")
    require(doc["checkpoint_15m"].strip(), "include the 15-minute observation or state that the run had ended")
    require(doc["cache"] in {"cold", "warm", "mixed"}, "record cache state")
    require(type(doc["cpu_limit"]) is int and doc["cpu_limit"] > 0 and
            type(doc["memory_gib"]) in (int, float) and doc["memory_gib"] > 0, "record actual run limits")
    for key in ("human_minutes", "uncached_input_tokens", "output_tokens", "cached_input_tokens", "compute_usd"):
        value = doc[key]
        require(value is None or type(value) in (int, float) and value >= 0, f"invalid cost: {key}")
    require(type(doc["assisted"]) is bool and doc["review_action"].strip(), "missing assistance or review action")
    lines = doc["maintainer_report"].splitlines()
    require(len(lines) == 5 and all(line.startswith(label + " ") and line[len(label):].strip()
                                     for label, line in zip(LABELS, lines)), "expected the five maintainer report lines")
    return seconds


def seal_report(source, destination):
    source = source.resolve(strict=True)
    doc = json.loads(source.read_bytes())
    check_operator(doc)
    # Store the report and evidence together. Replaying a seal must never overwrite the first report.
    root = destination / identifier(doc["build"])
    root.mkdir(parents=True, exist_ok=True)
    final = root / identifier(doc["case_id"])
    with tempfile.TemporaryDirectory(dir=root, prefix=".report-") as temp:
        prepared = Path(temp) / "sealed"
        prepared.mkdir()
        for item in doc["evidence"]:
            original = evidence_file(source.parent, item)
            dest = prepared / "evidence" / item["file"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, dest)
            evidence_file(prepared / "evidence", item)
        body = canonical(doc)
        (prepared / "operator.json").write_bytes(body)
        (prepared / "report.sha256").write_text(sha(body) + "\n")
        sealed = datetime.now(timezone.utc)
        require(timestamp(doc["finished_utc"]) <= sealed, "cannot seal a future report")
        (prepared / "seal.json").write_bytes(canonical({"report_sha256": sha(body), "sealed_utc": sealed.isoformat()}))
        # POSIX refuses to replace a non-empty directory. A repeated or concurrent publisher keeps the first.
        if final.exists():
            raise ValueError(f"first report already sealed: {doc['case_id']}")
        os.rename(prepared, final)
    return sha(body)


def roster(doc):
    rows = doc["cases"]
    require(doc["phase"] in {"main", "transfer"}, "unknown evaluation phase")
    require(len({identifier(row["case_id"]) for row in rows}) == len(rows), "duplicate case")
    for row in rows:
        for key in ("input_sha256", "reference_sha256"):
            hex_digest(row[key])
    if doc["phase"] == "main":
        require(Counter(r["stratum"] for r in rows) == {"change": 12, "preservation": 12},
                "primary denominator is twelve changes and twelve preservations")
    else:
        require(Counter((r["stratum"], r["family"]) for r in rows) ==
                {(s, f): 2 for s in ("change", "preservation") for f in ("same", "new")},
                "reserve needs two cases in each stratum/family combination")
    timestamp(doc["locked_utc"])
    return rows


def read_first(root, build, case, locked, product):
    folder = root / build / case["case_id"]
    body = (folder / "operator.json").read_bytes()
    digest = (folder / "report.sha256").read_text().strip()
    seal = json.loads((folder / "seal.json").read_bytes())
    require(sha(body) == digest, "sealed operator report changed")
    doc = json.loads(body)
    seconds = check_operator(doc)
    require((doc["case_id"], doc["build"], doc["input_sha256"], doc["product_sha256"]) ==
            (case["case_id"], build, case["input_sha256"], product), "case, artifact pair or product identity differs")
    require(timestamp(doc["intake_utc"]) >= locked, "operator saw case before cohort lock")
    require(seal["report_sha256"] == digest and timestamp(seal["sealed_utc"]) >= timestamp(doc["finished_utc"]),
            "invalid first report seal")
    for item in doc["evidence"]:
        evidence_file(folder / "evidence", item)
    return doc, digest, seconds, timestamp(seal["sealed_utc"])


def score(roster_doc, sealed, grades, build, product, budget, reveal_after, key):
    cases = roster(roster_doc)
    outcomes = []
    for case in cases:
        cid = case["case_id"]
        doc, digest, seconds, _ = sealed[cid]
        path = grades / build / (cid + ".json")
        grade = verified_document(path, key, "upgrade-adjudication-v1")
        require(grade["case_id"] == cid and grade["report_sha256"] == digest and
                grade["reference_sha256"] == case["reference_sha256"], "adjudication bound to different evidence")
        key.verify(bytes.fromhex(grade["reference_signature_hex"]),
                   SIGNATURE_CONTEXT + bytes.fromhex(case["reference_sha256"]))
        require(timestamp(grade["revealed_utc"]) >= reveal_after, "references opened before the last first report")
        reviews = grade["reviews"]
        require(len(reviews) >= 2 and len({r["reviewer"] for r in reviews}) == len(reviews), "independent grades required")
        decision = grade["decision"]
        for field in ("relevant", "scope_supported", "original_domain", "contradicted", "false_alert",
                      "unresolved_contradiction", "incremental_over_ci", "replayed", "nonvacuous"):
            require(type(decision[field]) is bool, f"missing adjudication of {field}")
        require(not decision["unresolved_contradiction"] or decision["contradicted"], "inconsistent contradiction grade")
        require(all(r["reason"].strip() and r["action"].strip() and isinstance(r["judgement"], dict) for r in reviews),
                "each reviewer must assess observation, evidence and action")
        require(all(r["judgement"] == decision for r in reviews) or grade.get("reconciliation", "").strip(),
                "independent graders disagree; written resolution required")
        require(grade["ci_result"].strip() and grade["action_grade"].strip(), "CI and review action must be graded")
        if grade.get("improved_capability"):
            evidence_file(path.parent, grade["improved_capability"]["evidence"])
        correct = decision["relevant"] and decision["scope_supported"] and decision["original_domain"]
        if case["stratum"] == "change":
            correct = correct and decision["replayed"] and doc["route"] not in {"open", "unavailable"}
        else:
            correct = correct and decision["nonvacuous"] and doc["route"] in {"native", "other-proof", "exhaustive-jvm"}
        measured = all(doc[k] is not None for k in ("human_minutes", "uncached_input_tokens", "output_tokens"))
        within = (measured and doc["cpu_limit"] == budget["cpus"] and doc["memory_gib"] == budget["memoryGiB"]
                  and seconds <= budget["wallSeconds"] and doc["human_minutes"] <= budget["humanReviewMinutes"]
                  and doc["uncached_input_tokens"] + doc["output_tokens"] <= budget["uncachedInputPlusOutputTokens"])
        credit = bool(correct and within and not doc["assisted"])
        require(credit or grade["primary_reason"].strip(), "a miss needs a reason")
        outcomes.append({"case_id": cid, "stratum": case["stratum"], "family": case.get("family"),
                         "credit": credit, "technicalResult": correct, "assisted": doc["assisted"], "route": doc["route"],
                         "seconds": seconds, "cache": doc["cache"], "environmentSha256": doc["environment_sha256"],
                         "cpuLimit": doc["cpu_limit"], "memoryGiB": doc["memory_gib"],
                         "firstActionableUtc": doc["first_actionable_utc"], "humanMinutes": doc["human_minutes"],
                         "computeUsd": doc["compute_usd"], "withinBudget": within, "decision": decision,
                         "improvedCapability": (grade.get("improved_capability") or {}).get("name"),
                         "action": grade["action_grade"], "ci": grade["ci_result"], "primaryReason": grade["primary_reason"]})
    def count(stratum):
        return sum(row["credit"] for row in outcomes if row["stratum"] == stratum)
    contradictions = sum(row["decision"]["contradicted"] for row in outcomes)
    unresolved = sum(row["decision"]["unresolved_contradiction"] for row in outcomes)
    return {"phase": roster_doc["phase"], "build": build, "productSha256": product, "denominator": len(cases),
            "relevantChange": count("change"), "relevantPreservation": count("preservation"),
            "contradictedAssurances": contradictions, "unresolvedContradictedAssurances": unresolved,
            "falseRoutineAlerts": sum(r["decision"]["false_alert"] for r in outcomes if r["stratum"] == "preservation"),
            "incrementalOverCI": sum(r["decision"]["incremental_over_ci"] for r in outcomes),
            "creditedRoutes": dict(Counter(r["route"] for r in outcomes if r["credit"])),
            "missesByPR": dict(Counter(r["primaryReason"] for r in outcomes if not r["credit"])),
            "pilotGate": roster_doc["phase"] == "main" and count("change") >= 8 and count("preservation") >= 8
                        and unresolved == 0, "cases": outcomes}


def paired(reports):
    old, new = reports
    require(old["phase"] == new["phase"] == "transfer" and old["productSha256"] != new["productSha256"],
            "two distinct frozen products required")
    after = {r["case_id"]: r for r in new["cases"]}
    counts = {f: Counter() for f in ("same", "new")}
    changes = []
    for prior in old["cases"]:
        current = after[prior["case_id"]]
        require((prior["stratum"], prior["family"]) == (current["stratum"], current["family"]),
                "transfer reference mismatch")
        for field in ("cache", "environmentSha256", "cpuLimit", "memoryGiB"):
            require(prior[field] == current[field], f"transfer conditions differ: {field}")
        result = {(True, True): "both", (True, False): "v0Only", (False, True): "v1Only",
                  (False, False): "neither"}[prior["credit"], current["credit"]]
        counts[prior["family"]][result] += 1
        changes.append({"case_id": prior["case_id"], "family": prior["family"], "stratum": prior["stratum"],
                        "result": result, "v0Seconds": prior["seconds"], "v1Seconds": current["seconds"],
                        "transferableRepair": current["improvedCapability"] if result == "v1Only" else None})
    return {"matchedCases": len(changes), "byFamily": {family: {k: v[k] for k in ("both", "v0Only", "v1Only", "neither")}
                                                        for family, v in counts.items()}, "cases": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    seal = commands.add_parser("seal-report")
    seal.add_argument("operator", type=Path)
    seal.add_argument("reports", type=Path)
    calc = commands.add_parser("score")
    calc.add_argument("roster", type=Path)
    calc.add_argument("reports", type=Path)
    calc.add_argument("grades", type=Path)
    calc.add_argument("--build", nargs=2, action="append", metavar=("ID", "LOCK_SHA256"), required=True)
    args = parser.parse_args()
    try:
        if args.operation == "seal-report":
            print(seal_report(args.operator, args.reports))
            return
        commitment = json.loads(Path(__file__).with_name("seed-commitment.json").read_text())
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(commitment["signer_ed25519_raw_hex"]))
        study = verified_document(args.roster, key, "upgrade-roster-v1")
        budget = json.loads(Path(__file__).with_name("budget.json").read_text())["declaredLimit"]
        require(len(args.build) == (1 if study["phase"] == "main" else 2), "wrong number of product builds")
        cases = roster(study)
        sealed = {}
        for build, lock in args.build:
            identifier(build)
            hex_digest(lock)
            require(build not in sealed, "duplicate product")
            if build == "V0":
                require(lock == sha(Path(__file__).with_name("v0.json").read_bytes()), "different V0 lock")
            if study["phase"] == "transfer":
                freeze = study["products"][build]
                require(freeze["lock_sha256"] == lock and
                        timestamp(freeze["frozen_utc"]) <= timestamp(study["release_utc"]),
                        "product changed after transfer release")
            # Across both products on transfer, verify every seal before reading even one grade.
            release = timestamp(study.get("release_utc", study["locked_utc"]))
            require(release >= timestamp(study["locked_utc"]), "case released before cohort lock")
            sealed[build] = {c["case_id"]: read_first(args.reports, build, c, release, lock)
                             for c in cases}
        reveal_after = max(row[3] for group in sealed.values() for row in group.values())
        results = [score(study, sealed[build], args.grades, build, lock, budget, reveal_after, key)
                   for build, lock in args.build]
        print(json.dumps({"builds": results, **({"paired": paired(results)} if len(results) == 2 else {})}, indent=2))
    except InvalidSignature:
        parser.exit(1, "Invalid curator signature.\n")
    except (KeyError, TypeError, OSError, ValueError) as exc:
        parser.exit(1, f"Scorecard unavailable: {exc}\n")


if __name__ == "__main__":
    main()
