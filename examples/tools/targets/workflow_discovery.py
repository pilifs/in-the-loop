"""W4's discovery projection: an external target's row in the index (examples/index.json's `target`, written by
build.py's render_index() through workflow.project()), which find.py's --family, --role, --readiness, --claim-status
and --gap read. Offline and read-only, from the sidecar, its files and the folder's receipts alone, as readiness() and
the handoff are: no process, no network, nothing written.

  family, role, case, tasks  what the sidecar states
  readiness                  the target's derived summary (workflow.readiness()): catalogued, partial, scaffolded,
                             executable or blocked (READINESS_IN_INDEX, below)
  taskReadiness              each task's summary, never a proof verdict
  expected                   each task's authored expected outcome: what the case states, never what was established
  claims                     each proof task's conclusion in its latest current receipt (established, refuted,
                             unresolved), or None without one; a replay decides no claim and isn't listed
  receipts                   each task's latest current receipt (path, attempt, execution, status, expectation) and
                             how many current attempts it has; earlier attempts stay in the folder
  staleReceipts, unreadable  receipts that no longer apply to the current inputs, or can't be read: listed, never counted
  gaps                       the kinds of the observed blockers whose evidence is there (find.py --gap)
  gapIds                     the gap ids those blockers' recorded verifier scans list
  unevidencedGaps            observed blockers whose packet file is missing: not counted as observed
  predictedGaps              predicted kinds: hypotheses until a probe reaches them
  historical                 the example's authored verdictLabel (a historical report's, for 105-109) with a note:
                             context only; no receipt or claim status is ever derived from it
  handoff                    the command that prints a task's handoff packet (workflow_handoff.py)

A historical report's label stays beside the projection, never inside `claims`: only a format-2 receipt filed by
ingestion, current for the task's inputs, gives a claim status.
"""

from pathlib import Path

from targets import workflow

# The target's readiness summary goes into the index's `readiness`. Phase 0's test_route.py expected None ("not
# derived yet") until the merge; Phase 5 step 1's request 5 turned this on, with that test expecting "catalogued". Off,
# the row says why in `unsupported` (HOLD).
READINESS_IN_INDEX = True
HOLD = ("readiness: derived (taskReadiness), and projected once the coordinator's test_route.py expects it at the "
        "merge (workflow_discovery.READINESS_IN_INDEX)")
HISTORICAL = ("the example's authored label, a historical report's or the case's own: context only; no receipt or "
              "claim status is derived from it")


def historical(example):
    label = example.get("verdictLabel")
    if label is None:
        return None
    return {"verdictLabel": label, "source": (example.get("source") or {}).get("url"), "note": HISTORICAL}


def gap_ids(folder, blocker):
    """The gap ids an observed blocker's packet file gives: from its recorded verifier scan, or as it states them."""
    from targets import workflow_handoff
    path = Path(folder) / blocker["packet"]
    document = workflow_handoff.read_json(path)
    if not isinstance(document, dict):
        return []
    try:
        diagnostic = workflow_handoff.recorded_scan(path, document).get("diagnostic") or document.get("diagnostic")
    except (AttributeError, TypeError, ValueError):
        return []
    return [d["id"] for d in diagnostic or [] if isinstance(d, dict) and isinstance(d.get("id"), str)]


def gaps(folder, target):
    """The sidecar's blockers, a task's or the target's, split as readiness splits them: an observed one counts when
    its packet file is there (or it names none), and is unevidenced when the file is missing."""
    observed, unevidenced, predicted, ids = set(), set(), set(), set()
    for b in target.get("handoff", {}).get("blockers", []):
        if not b["observed"]:
            predicted.add(b["kind"])
            continue
        if b.get("packet"):
            try:
                workflow.inside(folder, b["packet"])
            except workflow.ClaimError:
                unevidenced.add(b["kind"])
                continue
            ids.update(gap_ids(folder, b))
        observed.add(b["kind"])
    return {"gaps": sorted(observed), "gapIds": sorted(ids), "unevidencedGaps": sorted(unevidenced - observed),
            "predictedGaps": sorted(predicted)}


def project(folder, example, target):
    folder = Path(folder)
    identity = target["identity"]
    recorded = workflow.attempts(folder)
    ready = workflow.readiness(folder, example, target, recorded)
    by_path = {a["path"]: a for a in recorded}
    current = set()
    receipts, claims = {}, {}
    for t in target["tasks"]:
        paths = ready["tasks"][t["id"]]["receipts"]  # current for the task's inputs, in attempt order
        current.update(paths)
        if paths:
            latest = by_path[paths[-1]]
            receipts[t["id"]] = {"path": latest["path"], "attempt": latest["attempt"], "execution": latest["execution"],
                                 "status": latest["status"], "expectation": latest["expectation"],
                                 "attempts": len(paths)}
        if t["kind"] != "replay":
            claims[t["id"]] = receipts[t["id"]]["status"] if paths else None
    row = {
        "family": identity["family"],
        "role": identity["role"],
        "case": identity["case"],
        "tasks": [t["id"] for t in target["tasks"]],
        "readiness": ready["summary"] if READINESS_IN_INDEX else None,
        "taskReadiness": {k: v["summary"] for k, v in ready["tasks"].items()},
        "expected": {t["id"]: t.get("expected") for t in target["tasks"]},
        "claims": claims,
        "receipts": receipts,
        "staleReceipts": [a["path"] for a in recorded if not a["problem"] and a["path"] not in current],
        "unreadable": [a["path"] for a in ready["unreadable"]],
        **gaps(folder, target),
        "historical": historical(example),
        "handoff": f"python3 examples/tools/targets/workflow_handoff.py handoff {example.get('id')} TASK",
    }
    if not READINESS_IN_INDEX:
        row["unsupported"] = HOLD
    return row
