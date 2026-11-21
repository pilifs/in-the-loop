"""Map the original private case attempt into the project's existing first-report seal."""

import json
import sys

import runner_core as core
from runner_core import HERE

sys.path.insert(0, str(HERE.parents[1]))
import scorecard  # noqa: E402


def artifact_order(manifest):
    if not manifest:
        return {"old": [], "new": []}
    return {
        side: [r["sha256"] for r in manifest["artifacts"] if r["side"] in ("both", side)]
        for side in ("old", "new")
    }


def short(value, default=""):
    if isinstance(value, str):
        return value.strip() or default
    return json.dumps(value, ensure_ascii=False)[:800] if value else default


def build_document(info, root):
    m = info["measurement"]
    intake = m["intake"]
    report = info["report"]
    lines = report.splitlines()
    docs = info.get("verification", [])
    plan = info.get("primaryPlan") or {}
    claim = info.get("operatorClaim") or {}
    declared = claim.get("route", "open")
    classification = info["disposition"]
    artifacts = info.get("orderedArtifacts") or {"old": [], "new": []}
    allr = [r for d in docs for r in d.get("receipts", [])]
    native = info.get("eligibleNativeReceipts", [])
    archive = (
        sorted((root / "evidence-files").rglob("*")) if (root / "evidence-files").exists() else []
    )
    matched_jvm = [r for r in allr if r.get("jvmTwoSided")]
    domain_size = claim.get("finite_domain_size")
    if declared == "native":
        proof = bool(native)
    elif declared == "other-proof":
        proof = any(
            r.get("engine") in ("jbmc", "tlc")
            and r.get("status") in ("established", "refuted")
            and not r.get("vacuous")
            for r in allr
        )
    elif declared == "jvm-witness":
        proof = any(r.get("jvmObservationsDiffer") for r in matched_jvm)
    elif declared == "exhaustive-jvm":
        proof = (
            type(domain_size) is int
            and domain_size > 0
            and any(
                set(r.get("observationsPerRevision", {}).values()) == {domain_size}
                for r in matched_jvm
            )
        )
    else:
        proof = False
    if (
        classification == "reported"
        and declared in ("native", "other-proof", "jvm-witness", "exhaustive-jvm")
        and proof
        and archive
    ):
        route = declared
    elif plan and all(artifacts.values()):
        route = "open"
    else:
        route = "unavailable"
    if not all(artifacts.values()):
        route = "unavailable"
    first = (
        next(
            (
                e["at"]
                for e in (
                    json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()
                )
                if e["kind"] == "evidence" and e.get("observations")
            ),
            None,
        )
        if (root / "events.jsonl").is_file()
        else None
    )
    checkpoint = info["checkpoint"]
    checkpoint_text = (
        "Finished before 15 minutes."
        if checkpoint["finalBeforeCheckpoint"]
        else "At 15 minutes, the case was " + checkpoint["stage"] + "."
    )
    if checkpoint.get("lastEvidence"):
        checkpoint_text += " " + short(checkpoint["lastEvidence"].get("observations"))
    blocker = info.get("first_blocker") or (
        lines[2][len("Result ") :].strip() if route in ("open", "unavailable") else None
    )
    known_requests = m["requests"]
    measured_unknown = bool(m.get("reservedTokens"))

    def measure(k):
        return None if measured_unknown else sum(v["tokens"][k] for v in known_requests)

    uncached = (
        None
        if measured_unknown
        else sum(
            v["tokens"]["input_tokens"] + v["tokens"]["cache_creation_input_tokens"]
            for v in known_requests
        )
    )
    doc = {
        "case_id": info["case_id"],
        "build": "V0",
        "input_sha256": intake["pairSha256"],
        "product_sha256": info["productLockSha256"],
        "profile_sha256": info["profileSha256"],
        "environment_sha256": info["environmentSha256"],
        "route": route,
        "evidence": [],
        "primary_claim": short(
            claim.get("primary_claim") or plan.get("property"),
            lines[1][len("Caller-visible behavior ") :],
        ),
        "observer": short(
            claim.get("observer") or plan.get("entry"), lines[1][len("Caller-visible behavior ") :]
        ),
        "domain": short(claim.get("domain") or plan.get("bounds"), lines[3][len("Scope ") :]),
        "scope": short(claim.get("scope") or plan.get("boundary"), lines[3][len("Scope ") :]),
        "first_blocker": blocker,
        "artifacts": artifacts,
        "intake_utc": info["receivedAt"],
        "finished_utc": info["sealedAt"],
        "first_actionable_utc": first,
        "checkpoint_15m": checkpoint_text,
        "cache": "cold",
        "cpu_limit": int(info["resources"]["cpu"]),
        "memory_gib": info["resources"]["memoryBytes"] / 1024**3,
        "human_minutes": m["humanMinutes"],
        "uncached_input_tokens": uncached,
        "output_tokens": measure("output_tokens"),
        "cached_input_tokens": measure("cache_read_input_tokens"),
        "compute_usd": None if measured_unknown else m["estimatedUsd"],
        "assisted": bool(intake["assisted"]),
        "review_action": lines[4][len("Review action ") :],
        "maintainer_report": report,
        "resultRoute": info["resultRoute"],
        "disposition": classification,
        "cohort": intake["cohort"],
        "scheduler_mode": "one native request per fresh process, case-file continuation",
        "unmodified_continuous_team_session": False,
        "dependencies_sha256": intake["dependencySha256"],
        "product_revision": info.get("productRevision"),
        "checker_sha256": info.get("checkerSha256"),
        "measured_completed_requests": known_requests,
        "unsettled_reservation": m.get("reservedTokens", 0),
        "deadline_seconds": 7200,
        "checkpoint": checkpoint,
        "source_artifacts": info.get("sourceArtifacts"),
        "subject_jdk": info.get("subjectJdk"),
        "raw_operator_claim": claim,
        "verified_task_receipts": docs,
        "human_review_mode": "separate clean Fable session; external human interventions are supplied at intake",
    }
    for f in [
        root / "checkpoint-900.json",
        *sorted(root.glob("plan-*.json")),
        *sorted(root.glob("review-*.json")),
        *archive,
    ]:
        if f.is_file():
            doc["evidence"].append(
                {"file": f.relative_to(root).as_posix(), "sha256": core.isolation.digest(f)}
            )
    # A raw evidence directory or a declared route alone cannot support an assurance. Keep the original wording alongside the first blocker if the route cannot bind it.
    if (
        classification == "reported"
        and declared not in ("open", "unavailable")
        and route in ("open", "unavailable")
    ):
        doc["raw_maintainer_report"] = doc["maintainer_report"]
        doc["first_blocker"] = (
            "The declared evidence route did not bind eligible retained original receipts."
        )
        lines[2] = "Result Open. " + doc["first_blocker"]
        doc["maintainer_report"] = "\n".join(lines)
    scorecard.check_operator(doc)
    return doc


def store(source, dest):
    d = core.json_file(source)
    target = dest / d["build"] / d["case_id"]
    canonical = scorecard.sha(scorecard.canonical(d))
    if target.exists():
        if (target / "report.sha256").read_text().strip() != canonical:
            raise ValueError(
                "a different original report already owns the case in this scorecard store"
            )
        scorecard.check_operator(json.loads((target / "operator.json").read_bytes()))
        return canonical
    return scorecard.seal_report(source, dest)
