"""Check JVM origin, selected bytes, and a counterfactual swap on an archived invoice replay."""

import json
from dataclasses import replace
from pathlib import Path
import sys

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import interfaces, route, runtime, workflow_ingest


def audit():
    target = json.loads((FOLDER / "target.json").read_text())
    plan = route.resolve(FOLDER, json.loads((FOLDER / "example.json").read_text()), target, "replay")
    receipts = sorted((FOLDER / "receipts/replay").glob("*/result.json"))
    receipt = receipts[-1].parent
    attempt = json.loads((receipt.parent / "executions" / receipt.name / "attempt.json").read_text())
    bound, summaries = {}, {}
    for rev in plan.revisions:
        binding = attempt["bindings"][rev]
        chosen = binding["target"]["jvmClassOrigins"]["invoice.Rate"]
        holders = binding["target"]["orderedClasses"]["invoice.Rate"]
        assert chosen == holders[0]
        raw = (receipt / f"records/control-{rev}-jdk21.stdout").read_text().splitlines()
        rows = [json.loads(line) for line in raw]
        client = binding["target"]["classSha256"]
        assert all((r["rateClass"], r["rateJar"], r["invoiceClass"]) ==
                   (chosen["classSha256"], Path(chosen["path"]).name, client) for r in rows)
        rate = {"two-first": 2, "three-first": 3}[rev]
        assert [(row["q"], row["total"]) for row in rows] == [(q, q * rate) for q in range(-2, 3)]
        lock = runtime.lock(plan, rev)
        artifacts = tuple(interfaces.Artifact(**a) for a in binding["classpath"])
        bound[rev] = replace(lock, stage="artifacts-ready", artifacts=artifacts, classpath=tuple(a.path for a in artifacts))
        summaries[rev] = dict(clientClass=client, rateProviders=holders, codeSource=chosen["path"],
                              totals=[r["total"] for r in rows])
    before, after = plan.revisions
    assert summaries[before]["clientClass"] == summaries[after]["clientClass"]
    assert summaries[before]["rateProviders"] == list(reversed(summaries[after]["rateProviders"]))
    workflow_ingest.bound_revisions(plan, bound)
    original = bound[before]
    shadowed = [path for path in original.classpath if path.startswith("lib/")]
    bound[before] = replace(original, classpath=tuple(p for p in original.classpath if p not in shadowed)
                            + tuple(reversed(shadowed)))
    try:
        workflow_ingest.bound_revisions(plan, bound)
    except workflow_ingest.Refused as error:
        assert "different dependency order" in error.reason
        rejection = error.reason
    else:
        raise AssertionError("a receipt from the opposite closure qualified")
    return dict(replay=str(receipt.relative_to(FOLDER)), sides=summaries, rejectedSwap=rejection)


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
