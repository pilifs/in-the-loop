"""Run or recover one authorized upgrade. The trusted clock starts at the issuer's recorded intake time."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import jsonschema
import runner_core as core
from runner_core import HERE, Stopped, case_run, read_inside, write_inside
import isolation  # noqa: E402
import reporting  # noqa: E402
import identity  # noqa: E402
import freeze_evidence  # noqa: E402

LABELS = ("Upgrade", "Caller-visible behavior", "Result", "Scope", "Review action")
RESULTS = {
    "plan": "plan.json",
    "review": "review.json",
    "setup": "setup.json",
    "proof": "first-report.txt",
}


def origin_of(a):
    if not any((a.github, a.before, a.after)):
        return None
    if not (
        a.github
        and re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", a.github)
        and all(v and re.fullmatch("[0-9a-f]{40}", v) for v in [a.before, a.after])
    ):
        raise Stopped(
            "intake", "Incomplete or invalid review-time GitHub repository and revision pair."
        )
    return {"repository": a.github, "before": a.before, "after": a.after}


def memory_cpu():
    line = next(
        (s[3:] for s in Path("/proc/self/cgroup").read_text().splitlines() if s.startswith("0::")),
        None,
    )
    if line is None:
        raise ValueError("cgroup v2 is required for the declared resource cap")
    root = Path("/sys/fs/cgroup")
    here = root / line.lstrip("/")
    path = here
    memory = []
    cpus = []
    swaps = []
    while path.is_relative_to(root):
        for fname, items in [("memory.max", memory), ("memory.swap.max", swaps)]:
            f = path / fname
            if f.is_file() and (v := f.read_text().strip()) != "max":
                items.append(int(v))
        f = path / "cpu.max"
        if f.is_file():
            quota, period = f.read_text().split()
            if quota != "max":
                cpus.append(int(quota) / int(period))
        if path == root:
            break
        path = path.parent
    return {
        "cpu": min(cpus, default=None),
        "memoryBytes": min(memory, default=None),
        "swapBytes": min(swaps, default=None),
    }


def report_open(case_id, reason):
    detail = " ".join(str(reason).split())[:1400]
    return "\n".join(
        [
            f"Upgrade {case_id}",
            "Caller-visible behavior The original caller claim remains undecided.",
            "Result Open. " + detail,
            "Scope The released revision pair and its stated dependencies.",
            "Review action Read the first unverified step before relying on the upgrade claim.",
        ]
    )


def cohort_check(a, profile_hash, case_id, launch):
    if a.cohort == "disclosed":
        return
    if not a.cohort_release or not a.cohort_release_sha256:
        raise Stopped("cohort-unreleased", "This case has no owner-issued cohort lock.")
    if isolation.digest(a.cohort_release) != a.cohort_release_sha256:
        raise Stopped("cohort-unreleased", "The cohort release differs from the trusted lock.")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key = Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(
            core.json_file(HERE.parents[1] / "seed-commitment.json")["signer_ed25519_raw_hex"]
        )
    )
    try:
        study = reporting.scorecard.verified_document(a.cohort_release, key, "upgrade-roster-v1")
        rows = reporting.scorecard.roster(study)
    except Exception as exc:
        raise Stopped(
            "cohort-unreleased", "The issuer signature or cohort shape was rejected."
        ) from exc
    if study.get("profile_sha256") != profile_hash or core.timestamp(
        study["locked_utc"]
    ) > core.timestamp(a.received_at):
        raise Stopped("cohort-unreleased", "The profile was not locked before case intake.")
    phase = "main" if a.cohort == "scored" else "transfer"
    if phase == "main" and launch["build"] != "V0":
        raise Stopped("cohort-unreleased", "The main cohort requires its frozen V0 product.")
    if phase == "transfer":
        freeze = study.get("products", {}).get(launch["build"], {})
        if (
            freeze.get("lock_sha256") != launch["product_sha256"]
            or not freeze.get("frozen_utc")
            or core.timestamp(freeze["frozen_utc"]) > core.timestamp(study["release_utc"])
            or core.timestamp(study["release_utc"]) > core.timestamp(a.received_at)
        ):
            raise Stopped(
                "cohort-unreleased",
                "The signed transfer release does not bind this frozen build at intake.",
            )
    matches = [
        row for row in rows if row["case_id"] == case_id and row["input_sha256"] == a.pair_sha256
    ]
    if len(matches) != 1 or phase != study["phase"]:
        raise Stopped(
            "cohort-unreleased", "The signed roster does not bind this neutral case to this phase."
        )
    if a.dependencies and matches[0]["artifacts"] != reporting.artifact_order(
        core.json_file(a.dependencies)
    ):
        raise Stopped(
            "cohort-unreleased", "The ordered dependency closure differs from the signed roster."
        )


def fresh_view(a, path):
    return isolation.fresh_case(path, a.release, a.pair_sha256, a.dependencies, a.dependency_sha256)


def role_stage(
    stage, case, a, ledger, profile, origin, prompt_note, validator, model_call=core.model_request
):
    stage_text = core.json_file(HERE / "stages.json")[stage]
    model = profile["roles"][stage]["model"]
    ledger.phase(stage)
    continuation = False
    correction = ""
    while True:
        ledger.require_time()
        if continuation:
            task = (
                "Continue your same native "
                + stage
                + " conversation from its previous results. Finish the required /case/work/"
                + RESULTS[stage]
                + " in the isolated case. "
                + correction
            )
        else:
            task = (
                profile["neutralPrompt"]
                + "\n\n"
                + stage_text
                + "\n"
                + prompt_note
                + "\nReview-time source: "
                + (
                    json.dumps(origin)
                    if origin
                    else "local neutral source supplied in the separately assisted lane"
                )
                + "\nUse only case_command, with an argv array. The released pair is /case/packet and any dependency manifest is /case/dependencies/manifest.json. Your current-stage session and case files persist. Write /case/work/open.json with a precise reason for the first unsupported original operation. "
            )
        model_call(model, stage, task, a.product, case, ledger, a.claude)
        continuation = True
        opened = read_inside(a.product, case, "/case/work/open.json", ledger)
        if opened:
            try:
                reason = json.loads(opened)["reason"]
            except (ValueError, KeyError, TypeError):
                reason = ""
            if isinstance(reason, str) and reason.strip():
                raise Stopped("open-" + stage, reason[:1400])
        text = read_inside(a.product, case, "/case/work/" + RESULTS[stage], ledger)
        problem = ""
        if text:
            if stage == "proof":
                core.exclusive(ledger.root / "first-model-submission.txt", text.encode())
            try:
                value = validator(text)
            except (
                ValueError,
                KeyError,
                TypeError,
                AssertionError,
                jsonschema.ValidationError,
            ) as exc:
                problem = str(exc).splitlines()[0][:400]
            else:
                ledger.event(
                    "stage-complete",
                    stage=stage,
                    artifactSha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                return value, text
        correction = (
            "Correct the stage artifact: " + problem
            if problem
            else "The required artifact has not yet appeared."
        )


def check_review(text):
    value = json.loads(text)
    if (
        value.get("decision") not in ("approve", "revise", "open")
        or not isinstance(value.get("reason"), str)
        or not value["reason"].strip()
    ):
        raise ValueError("Review needs decision and reason.")
    return value


def check_setup(text):
    value = json.loads(text)
    tasks = value.get("tasks")
    if (
        not isinstance(tasks, list)
        or not tasks
        or len(tasks) != len(set(tasks))
        or not all(isinstance(t, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", t) for t in tasks)
        or not value.get("subjectJdk")
    ):
        raise ValueError("Setup needs distinct product task IDs and a subjectJdk.")
    return value


def check_report(text):
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    if len(lines) != 5 or any(not line.startswith(label + " ") for line, label in zip(lines, LABELS)):
        raise ValueError("Use exactly the five maintainer-report lines.")
    return "\n".join(lines)


def qualified_tasks(a, case, budget, origin, setup):
    target = json.loads(
        read_inside(a.product, case, "/opt/product/examples/001-case/target.json", budget)
    )
    history = target.get("history", {})
    revisions = history.get("revisions", {})
    if not a.assisted_local_source_bridge:
        if (
            history.get("repository") != origin["repository"]
            or not {origin["before"], origin["after"]}.issubset(
                {v.get("commit") for v in revisions.values()}
            )
            or target.get("preparation", {}).get("route") == "fixture"
            or any("fixture" in x for x in revisions.values())
        ):
            raise Stopped(
                "original-intake",
                "The proposed setup does not bind the original GitHub revision pair through an original product route.",
            )
    listing = {t["id"]: t for t in target["tasks"]}
    receipts = []
    budget.phase("verification")
    for task in setup["tasks"]:
        if task not in listing:
            raise Stopped("setup", "The declared task is absent from the product sidecar.")
        cmd = ["python3", "/opt/product/examples/tools/build.py"]
        planned = case_run(a.product, case, cmd + ["--plan", "001", "--task", task], budget)
        if planned["exit"]:
            raise Stopped("planning", planned["output"][-800:])
        plan = json.loads(planned["output"])[0]
        if not plan.get("executable"):
            raise Stopped(
                "unsupported", str(plan.get("notExecuted", "The product plan could not execute."))
            )
        before = freeze_evidence.initial(a.product, case, task, budget)
        start = time.monotonic()
        result = case_run(a.product, case, cmd + ["001", "--task", task], budget)
        # Read the receipts in the guest after the trusted invocation. Host paths can never be supplied by case code.
        script = """import hashlib,json,pathlib,sys
p=pathlib.Path('/opt/product/examples/001-case/receipts')/sys.argv[1]
def digest(f): return hashlib.sha256(f.read_bytes()).hexdigest()
rows=[]
for f in sorted(p.glob('*/result.json')):
 d=json.loads(f.read_bytes()); a=d.get('attempt',{}); e=d.get('evidence',{}); c=d.get('conclusion',{}); rows.append({'receipt':str(f.relative_to(p.parent.parent)),'sha256':digest(f),'status':c.get('status'),'label':c.get('label'),'vacuous':c.get('vacuous'),'checker':a.get('tools',{}).get('jvmcontract'),'engine':a.get('engine'),'problem':str(e.get('problem') or '')[:500],'claim':d.get('claim',{}).get('id')})
print(json.dumps(rows))"""
        observed = case_run(a.product, case, ["python3", "-c", script, task], budget)
        rows = json.loads(observed["output"]) if not observed["exit"] else []
        rows = freeze_evidence.save(a.product, case, task, rows, before, budget)
        summary = {
            "task": task,
            "exit": result["exit"],
            "seconds": round(time.monotonic() - start, 3),
            "outputTail": result["output"][-1200:],
            "receipts": rows,
            "planSha256": hashlib.sha256(planned["output"].encode()).hexdigest(),
        }
        receipts.append(summary)
        budget.event("evidence", task=task, exit=result["exit"], observations=rows)
    return receipts


def run(a, profile, profile_hash, resources):
    launch, launch_hash = identity.load_launch(a.launch_lock, a.launch_sha256, profile_hash)
    valid_id = a.case_id or "unreadable-neutral-pair"
    try:
        if isolation.digest(a.release / "pair.json") == a.pair_sha256:
            valid_id = core.json_file(a.release / "pair.json")["case_id"]
    except (ValueError, KeyError, OSError):
        pass
    intake = {
        "case_id": valid_id,
        "receivedAt": a.received_at,
        "cohort": a.cohort,
        "build": launch["build"],
        "launchLockSha256": launch_hash,
        "pairSha256": a.pair_sha256,
        "dependencySha256": a.dependency_sha256,
        "humanMinutes": a.human_minutes,
        "assisted": a.assisted_local_source_bridge,
        "github": a.github,
        "before": a.before,
        "after": a.after,
    }
    ledger = core.Ledger(a.case_dir, intake, profile, profile_hash)
    ledger.shadow_product = a.shadow_product
    route = "assisted-local-source-bridge" if a.assisted_local_source_bridge else "original-product"
    extra = {
        "resources": resources,
        "build": launch["build"],
        "productLockSha256": launch["product_sha256"],
        "environmentSha256": launch["environment_sha256"],
        "environmentVerified": False,
        "launchLockSha256": launch_hash,
        "stagedRootSha256": None,
        "expectedStagedRootSha256": launch["staged_root_sha256"],
        "productRevision": launch["revision"],
        "checkerSha256": launch["checker_sha256"],
        "regularFirstReportEligible": not a.assisted_local_source_bridge,
    }
    try:
        if (a.case_dir / "first-report.json").exists():
            sealed = core.json_file(a.case_dir / "first-report.json")
            core.exclusive(
                a.case_dir / "first-report.sha256",
                (isolation.digest(a.case_dir / "first-report.json") + "\n").encode(),
            )
            return sealed
        if ledger.existing:
            raise Stopped(
                "interrupted",
                "A previous worker left an unsealed original attempt. The last durable phase and any outstanding model reservation are preserved.",
            )
        ledger.event("intake", cohort=a.cohort)
        core.exclusive(a.case_dir / "product-launch.json", a.launch_lock.read_bytes())
        if (a.product / "manifest.json").is_file():
            extra["stagedRootSha256"] = isolation.digest(a.product / "manifest.json")
        actual, env = identity.inspect_root(a.product, resources)
        core.exclusive(a.case_dir / "matched-environment.json", isolation.canonical(env))
        extra["environmentSha256"] = actual["environment_sha256"]
        extra["environmentVerified"] = True
        if any(launch[key] != value for key, value in actual.items()):
            raise Stopped(
                "product-pin",
                "The measured build or environment differs from its separate frozen launch lock.",
            )
        ledger.require_time()
        cohort_check(a, profile_hash, valid_id, launch)
        if a.human_minutes < 0 or a.human_minutes > profile["budget"]["humanReviewMinutes"]:
            raise Stopped(
                "human-budget", "The recorded human review time exceeds the pre-registered limit."
            )
        for path, expected in profile.get("runnerSha256", {}).items():
            if isolation.digest(HERE / path) != expected:
                raise Stopped(
                    "runner-pin",
                    "The frozen first-party execution profile has a different implementation.",
                )
        origin = origin_of(a)
        case = a.case_dir / "application"
        release = fresh_view(a, case)
        extra["sourceArtifacts"] = release
        if a.dependencies:
            extra["orderedArtifacts"] = reporting.artifact_order(
                core.json_file(case / "dependencies/manifest.json")
            )
        if release["case_id"] != valid_id:
            raise Stopped("intake", "The released case ID differs from the trusted intake.")
        if not origin and not a.assisted_local_source_bridge:
            raise Stopped(
                "original-intake",
                "The pinned official workflow accepts GitHub commit pairs. The issuer released only neutral local trees. No original public pair or supported registered example is available on this intake.",
            )
        if not a.claude or isolation.digest(a.claude) != profile["client"]["sha256"]:
            raise Stopped("client-pin", "The exact qualified Claude executable is unavailable.")
        if (
            not Path("/srv").is_dir()
            or any(Path("/srv").iterdir())
            or any(
                Path(n).exists()
                for n in (
                    "/CLAUDE.md",
                    "/AGENTS.md",
                    "/.claude",
                    "/etc/claude-code/managed-settings.json",
                    "/etc/claude-code/managed-settings.d",
                )
            )
        ):
            raise Stopped(
                "control-workspace",
                "The qualified neutral client working directory or managed-settings boundary differs.",
            )
        if (
            not (a.shadow_product / "manifest.json").is_file()
            or isolation.digest(a.shadow_product / "manifest.json")
            != profile["shadow"]["toolRootSha256"]
        ):
            raise Stopped(
                "shadow-tool-pin",
                "The isolated credentialless native context meter does not match its pinned root.",
            )
        schema = core.json_file(a.product / "root/opt/product/llm-dlc/prove-plan.schema.json")

        def check_plan(text):
            v = json.loads(text)
            jsonschema.validate(v, schema)
            return v

        feedback = ""
        revision = 0
        while True:
            if revision:
                case_run(
                    a.product,
                    case,
                    [
                        "python3",
                        "-c",
                        "from pathlib import Path;Path('/case/work/plan.json').unlink(missing_ok=True)",
                    ],
                    ledger,
                )
            plan, plantext = role_stage(
                "plan", case, a, ledger, profile, origin, feedback, check_plan
            )
            extra["primaryPlan"] = next(iter(plan.get("examples", [])), {})
            reviewer = a.case_dir / f"reviewer-{revision}"
            fresh_view(a, reviewer)
            write_inside(a.product, reviewer, "/case/work/plan.json", plantext, ledger)
            review, reviewtext = role_stage(
                "review",
                reviewer,
                a,
                ledger,
                profile,
                origin,
                "Review only this proposal and original released material.",
                check_review,
            )
            core.exclusive(a.case_dir / f"plan-{revision}.json", plantext.encode())
            core.exclusive(a.case_dir / f"review-{revision}.json", reviewtext.encode())
            if review["decision"] == "open":
                raise Stopped("claim-review", review["reason"])
            if review["decision"] == "approve":
                break
            feedback = "Independent reviewer requested revision: " + review["reason"][:1200]
            revision += 1
        if not plan.get("examples"):
            raise Stopped(
                "plan-set-aside",
                "The reviewed original plan set the change aside: "
                + str(plan.get("setAside", "no supported claim"))[:1100],
            )
        write_inside(a.product, case, "/case/work/review.json", reviewtext, ledger)
        setup, _ = role_stage(
            "setup",
            case,
            a,
            ledger,
            profile,
            origin,
            "Use only claims approved in review. Report the actual subject JDK.",
            check_setup,
        )
        evidence = qualified_tasks(a, case, ledger, origin, setup)
        write_inside(a.product, case, "/case/work/verification.json", json.dumps(evidence), ledger)
        extra["verification"] = evidence
        extra["subjectJdk"] = setup["subjectJdk"]
        report, _ = role_stage(
            "proof",
            case,
            a,
            ledger,
            profile,
            origin,
            "The controller ran the standard tasks. Use /case/work/verification.json and the actual product receipts.",
            check_report,
        )
        result_rows = [
            r
            for task in evidence
            for r in task["receipts"]
            if r.get("checker") == launch["checker_sha256"]
            and r.get("status") in ("established", "refuted")
            and not r.get("vacuous")
        ]
        extra["eligibleNativeReceipts"] = result_rows
        claim_text = read_inside(a.product, case, "/case/work/claim-evidence.json", ledger)
        if claim_text:
            extra["operatorClaim"] = json.loads(claim_text)
        return ledger.seal(route, "reported", report, extra)
    except Stopped as exc:
        return ledger.seal(route, exc.code, report_open(valid_id, exc.detail), extra)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as exc:
        return ledger.seal(
            route,
            "case-setup-error",
            report_open(
                valid_id,
                "The original attempt stopped at " + type(exc).__name__ + ": " + str(exc)[:500],
            ),
            extra,
        )
    finally:
        ledger.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ("release", "product", "case-dir"):
        p.add_argument("--" + option, type=Path, required=True)
    p.add_argument(
        "--reports",
        type=Path,
        required=True,
        help="scorecard first-report store; use a different store for assisted diagnostics",
    )
    p.add_argument("--shadow-product", required=True, type=Path)
    p.add_argument("--launch-lock", type=Path, default=identity.DEFAULT_LAUNCH)
    p.add_argument(
        "--launch-sha256", help="trusted out-of-band digest, required for alternate build locks"
    )
    p.add_argument("--pair-sha256", required=True)
    p.add_argument("--dependencies", type=Path)
    p.add_argument("--dependency-sha256")
    p.add_argument("--received-at", required=True)
    p.add_argument("--cohort", choices=("disclosed", "scored", "transfer"), required=True)
    p.add_argument("--github")
    p.add_argument("--before")
    p.add_argument("--after")
    p.add_argument("--case-id")
    p.add_argument("--assisted-local-source-bridge", action="store_true")
    p.add_argument("--cohort-release", type=Path)
    p.add_argument("--cohort-release-sha256")
    p.add_argument("--human-minutes", type=float, default=0)
    p.add_argument("--scope-active", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    a.reports = a.reports.resolve()
    a.release = a.release.resolve()
    a.product = a.product.resolve()
    a.shadow_product = a.shadow_product.resolve()
    a.case_dir = a.case_dir.resolve()
    a.claude = Path(shutil.which("claude")).resolve() if shutil.which("claude") else None
    a.launch_lock = a.launch_lock.resolve()
    path = identity.PROFILE
    profile = core.json_file(path)
    profile_hash = isolation.digest(path)
    if core.timestamp(a.received_at) > time.time() + 1:
        p.error("intake time cannot be in the future")
    if a.dependencies:
        a.dependencies = a.dependencies.resolve()
    if a.assisted_local_source_bridge and a.cohort != "disclosed":
        p.error(
            "store case-specific assistance in a separate disclosed diagnostic; never convert or overwrite a scored original"
        )
    if a.cohort_release:
        a.cohort_release = a.cohort_release.resolve()
    if len(set(x for x in [a.release, a.product, a.case_dir] if x)) != 3 or any(
        a.case_dir.is_relative_to(x) or x.is_relative_to(a.case_dir) for x in (a.release, a.product)
    ):
        p.error("input, tool and private case storage must be independent locations")
    measured = memory_cpu()
    matched = (
        measured["cpu"] == 4
        and measured["memoryBytes"] == 16 * 1024**3
        and measured["swapBytes"] == 0
    )
    if not a.scope_active and not matched:
        return subprocess.run(
            [
                "systemd-run",
                "--user",
                "--scope",
                "-q",
                "-p",
                "CPUQuota=400%",
                "-p",
                "MemoryMax=16G",
                "-p",
                "MemorySwapMax=0",
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                "--scope-active",
            ]
        ).returncode
    resources = memory_cpu()
    if (
        resources["cpu"] != 4
        or resources["memoryBytes"] != 16 * 1024**3
        or resources["swapBytes"] != 0
    ):
        raise SystemExit(
            "The published run requires a 4-CPU, 16-GiB, zero-swap cgroup. No model was called."
        )
    try:
        r = run(a, profile, profile_hash, resources)
    except BlockingIOError:
        raise SystemExit("This case already has an active worker.")
    packet_sha = reporting.store(a.case_dir / "first-report.json", a.reports)
    print(
        json.dumps(
            {
                "scorecard_sha256": packet_sha,
                "case_id": r["case_id"],
                "disposition": r["disposition"],
                "profile": profile_hash,
                "sealed": str(a.case_dir / "first-report.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
