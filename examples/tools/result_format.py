"""The format of an example's stored result.json, and the view the renderer reads it through.

Every format question is in this module, so a later change to the format is a change here and nowhere else.

Format 1 is the flat result: every field at the top level. Every result recorded before format 2 has it, and it
carries no `format` field. Since step 3b it may also carry `claim`, `attempt`, `conclusion` and `bundle` next to the
flat fields, which then repeat what those blocks say.

Format 2 (`"format": 2`) stores each fact once:

- `claim`, `attempt` and `bundle` are as in format 1. The run's `execution` lives only in `attempt.execution`.
- `conclusion` holds the verdict as `status` (established, refuted, unresolved, or null without a verdict), its
  `label`, `vacuous` and `expectation`. Its `obligations` each carry a `kind` and the obligation's own `evidence`:
  a B11 property's record (`property`), a D1 configuration's (`configuration`), a generated operator's contract as
  built (`operator-contract`). `obligationKeys` says which flat field each kind is shown as.
- `evidence` holds everything else the run found, under the flat names. That covers the excerpts, the existing tests,
  the counterexamples, the trace, the coverage and the files. It also holds B11's headline fields (`property`,
  `domain`, `proof`, `problem`, `statement`, the first refuted property's, else the first unresolved, else the first).
  Those are a summary of the obligations, kept here because the runner derives them together with how the run
  ended. Format 3 drops them (see below).

view() turns any stored format into the flat result the renderer, the router and the checks read. For format 1 it
is the document itself. pack() turns a run's flat result into format 2, and the round trip view(pack(r)) == r is
checked before anything is published, so storing format 2 loses nothing.

Moving to the next format (Option C of the brief's open question 1, once the pipeline has run every example again):
- Write the renderer against the stored document instead of view(). The obligations' evidence becomes primary, and
  B11's headline fields are computed from it, then removed from `evidence`.
- Add the new format to VIEWS, or replace view() with reads of the document. Retire VIEWS[1] once no committed
  result has format 1: `python3 examples/tools/result_format.py` counts the stored formats.
"""

import json
import sys
from pathlib import Path

FORMAT = 2  # the format build.py stores

CONCLUSION = {"verified": "established", "violation": "refuted", "unverifiable": "unresolved"}
VERDICT = {status: verdict for verdict, status in CONCLUSION.items()}

# Each kind of obligation and the flat field the obligations of that kind are shown as, in order.
OBLIGATION_KEYS = {"property": "properties", "configuration": "configurations", "operator-contract": "modelContracts"}

# Flat fields format 2 stores elsewhere, or derives: they are never in `evidence`.
BLOCKS = ("claim", "attempt", "conclusion", "bundle")
DERIVED = ("verdict", "verdictLabel", "execution", "expectation", "matchesExpected")


def stored_format(document):
    return document.get("format", 1)


def obligations(result):
    """The obligations a flat result checked, each with its kind, name, statement, status and own evidence: each
    property of a B11 target, each configuration of a D1 model, each generated operator's contract as built."""
    out = []
    for i, q in enumerate(result.get("properties") or [], 1):
        out.append({"kind": "property", "name": q.get("harness") or f"property-{i}", "statement": q["assert"],
                    "status": CONCLUSION.get(q["verdict"]), "evidence": q})
    for c in result.get("configurations") or []:
        out.append({"kind": "configuration", "name": c["label"], "statement": c["cfg"],
                    "status": CONCLUSION.get(c["verdict"]) if c.get("status") == "completed" else None, "evidence": c})
    for m in result.get("modelContracts") or []:
        out.append({"kind": "operator-contract", "name": m["symbol"],
                    "statement": "the contract the operator is generated from, as built",
                    "status": "established" if m["connection"] == "verified" or m.get("allowed") else "refuted",
                    "evidence": m})
    return out


def conclusion_record(claim, attempt, result):
    """The conclusion a flat result shows (format 1's block): the claim and attempt it is about, the status, vacuity
    and expectation, and each obligation without its evidence."""
    status = CONCLUSION.get(result["verdict"]) if result["verdict"] else None
    return {"claim": claim["id"], "attempt": attempt["id"], "status": status,
            "vacuous": bool((result.get("coverage") or {}).get("vacuous")), "expectation": result["expectation"],
            "obligations": [{k: o[k] for k in ("name", "statement", "status")} for o in obligations(result)]}


def pack(result):
    """A run's flat result, with its claim, attempt, conclusion and bundle, as format 2: each fact stored once."""
    missing = [k for k in BLOCKS if not result.get(k)]
    if missing:
        raise ValueError(f"a result without {', '.join(missing)} cannot be stored as format {FORMAT}")
    if result["conclusion"].get("status") != (CONCLUSION.get(result["verdict"]) if result["verdict"] else None):
        raise ValueError("the result's verdict and its conclusion disagree")
    if result["attempt"].get("execution") != result["execution"]:
        raise ValueError("the result's execution and its attempt's disagree")
    # A list of obligations is stored in them; an empty or null one stays in `evidence` as it was, so that the view
    # shows the field exactly as the run left it.
    moved = {key for key in OBLIGATION_KEYS.values() if result.get(key)}
    evidence = {k: v for k, v in result.items() if k not in BLOCKS and k not in DERIVED and k not in moved}
    conclusion = {**result["conclusion"], "label": result["verdictLabel"],
                  "obligationKeys": {kind: key for kind, key in OBLIGATION_KEYS.items() if key in moved},
                  "obligations": obligations(result)}
    return {"format": FORMAT, "claim": result["claim"], "attempt": result["attempt"], "conclusion": conclusion,
            "evidence": evidence, "bundle": result["bundle"]}


def view_2(document):
    c = document["conclusion"]
    flat = dict(document["evidence"])
    for kind, key in c["obligationKeys"].items():
        flat[key] = [o["evidence"] for o in c["obligations"] if o["kind"] == kind]
    flat.update({"verdict": VERDICT.get(c["status"]) if c["status"] else None, "verdictLabel": c["label"],
                 "execution": document["attempt"]["execution"], "expectation": c["expectation"],
                 "matchesExpected": c["expectation"] == "yes",
                 "claim": document["claim"], "attempt": document["attempt"], "bundle": document["bundle"],
                 "conclusion": {**{k: v for k, v in c.items() if k not in ("label", "obligationKeys", "obligations")},
                                "obligations": [{k: o[k] for k in ("name", "statement", "status")} for o in c["obligations"]]}})
    return flat


VIEWS = {1: lambda document: document, 2: view_2}


def view(document):
    """The flat result of a stored document of any known format."""
    fmt = stored_format(document)
    if fmt not in VIEWS:
        raise ValueError(f"result format {fmt} is not one build.py reads (it reads {', '.join(map(str, sorted(VIEWS)))})")
    return VIEWS[fmt](document)


def load(path):
    """The flat result stored at `path`, of any known format: the one way results are read back."""
    return view(json.loads(Path(path).read_text()))


def round_trip_problems(result):
    """Why storing a flat result as format 2 would lose or change something, or an empty list."""
    try:
        back = view(json.loads(json.dumps(pack(result), ensure_ascii=False)))
    except (ValueError, KeyError, TypeError) as e:
        return [str(e)]
    canonical = json.loads(json.dumps(result, ensure_ascii=False))
    return [f"`{k}` would be stored as {json.dumps(back.get(k))[:80]} for {json.dumps(canonical.get(k))[:80]}"
            for k in sorted(set(back) | set(canonical)) if back.get(k, KeyError) != canonical.get(k, KeyError)]


if __name__ == "__main__":
    # How many committed results have each format: format 1 can be retired when it has none.
    examples = Path(__file__).resolve().parents[1]
    counts = {}
    for f in sorted(examples.glob("[0-9][0-9][0-9]-*/result.json")):
        fmt = stored_format(json.loads(f.read_text()))
        counts.setdefault(fmt, []).append(f.parent.name[:3])
    for fmt, ids in sorted(counts.items()):
        print(f"format {fmt}: {len(ids)} result(s)" + (f" ({', '.join(ids)})" if len(ids) <= 12 else ""))
    sys.exit(0)
