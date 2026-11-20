"""Read the recorded synthetic checks. Exit nonzero whenever the normal model tool boundary is unverified."""

import argparse
import json
from pathlib import Path

import isolation


def assess(namespace, stock, pin):
    reasons = []
    checks = namespace["caseChecks"]
    fixed = {
        "positiveRead",
        "positiveWrite",
        "networkUnavailable",
        "noEffectiveCapabilities",
        "noNewPrivileges",
        "privatePidNamespace",
        "environmentAllowlisted",
    }
    outside = {
        "sibling-packet",
        "curator-reference",
        "historical-transcript",
        "hidden-test",
        "knowledge-base",
        "prior-report",
        "host-repository",
        "host-docker",
        "host-config",
    }
    if (
        not all(checks.get(k) is True for k in fixed)
        or not all(checks.get("outsideBlocked", {}).get(k) is True for k in outside)
        or not all(checks.get("readOnly", {}).get(k) is True for k in ("packet", "product"))
    ):
        reasons.append("filesystem, process or network isolation failed")
    if (
        namespace["revision"] != pin["revision"]
        or namespace["checkerSha256"] != pin["sha256"]["jvmcontract"]
        or not namespace["freshSecondCase"]
        or not namespace["v0Handoff"]
        or namespace.get("nativeVerification")
        != {"status": "established", "checker": pin["sha256"]["jvmcontract"], "engine": "native"}
    ):
        reasons.append("pinned V0 or fresh-case native proof evidence missing")
    if not stock["controlSideAuthenticated"] or stock["controlSideAuthStatusExit"] != 0:
        reasons.append("control-side login unavailable")
    for role in ("preparation", "plannerAndProver"):
        row = stock["stages"][role]
        if row["model"] != pin[role]["model"] or not row["caseMcpNamespaceMentioned"]:
            reasons.append(role + " missing the selected model or case tool")
        if (
            row["exactCaseToolOnly"] is not True
            or row["nestedFileOrNetworkTools"]
            or set(row["namespaces"]) != {"mcp__neutral_case__case_command"}
        ):
            native = ", ".join(row["nestedFileOrNetworkTools"]) or "unqualified native tools"
            cooperation = ", ".join(row["namespaces"].get("collaboration", []))
            reasons.append(
                f"{role} also exposes {native}; cross-thread methods: {cooperation or 'none recorded'}. Their confinement on the normal service has not been demonstrated."
            )
    return {"scoredLaunchEligible": not reasons, "reasons": reasons}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--namespace", type=Path, default=isolation.HERE / "evidence/namespace.json")
    p.add_argument("--stock", type=Path, default=isolation.HERE / "evidence/stock-codex.json")
    args = p.parse_args()
    try:
        result = assess(
            json.loads(args.namespace.read_bytes()),
            json.loads(args.stock.read_bytes()),
            json.loads(isolation.PIN.read_bytes()),
        )
    except (OSError, ValueError, KeyError, TypeError) as err:
        result = {
            "scoredLaunchEligible": False,
            "reasons": ["missing or invalid qualification evidence: " + str(err)],
        }
    print(json.dumps(result, indent=2))
    return 0 if result["scoredLaunchEligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
