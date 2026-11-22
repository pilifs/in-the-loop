"""Recount the domain follow-up from collected jobs, including the first refusals and timeouts."""
import argparse
from collections import Counter
import json
from pathlib import Path

from results import DATA, ROOT, Job, native, original_scope, read, rel, repeated_decimal, sha

IDS = {
    "enumOnly": "20261122-024332-check-javaparser-traversals-with-only-th",
    "firstSchema": "20261122-025719-check-avro-reserved-names-and-original-s",
    "nonemptyRetry": "20261122-025941-resolve-the-nonempty-javaparser-parent-w",
    "explicitSeparator": "20261122-030646-prove-javaparser-startup-for-supplied-an",
    "schema": "20261122-030957-confirm-both-avro-schema-producers-and-f",
    "beforeTables": "20261122-031102-recheck-original-startup-scopes-after-th",
    "jackson": "20261122-032239-qualify-ordinary-jackson-table-startup-o",
    "final": "20261122-032303-repeat-frozen-claims-on-the-jackson-tabl",
}
ORIGINAL = {
    "355": ["direct-limit-fix","full-length-parent","full-length-fix","prefix-parent","prefix-fix","bounds-fix","rejected-fix"],
    "360": ["postorder-fix","terminal-fix","preorder-parent","preorder-fix","nonempty-parent","nonempty-fix"],
    "361": ["cursor-parent","cursor-fix","decimals-parent","decimals-fix"],
}


def comparison(job, ordinary, decimal, historical, adoption):
    rows, fingerprints = {}, set()
    for number, tasks in ORIGINAL.items():
        rows[number] = {}
        for task in tasks:
            r = native(job, ordinary, task)
            if r["startup"]: raise ValueError("an original claim includes a startup capture")
            fingerprints.add(r["checker"]["jvmcontract"])
            rows[number][task] = {k:r[k] for k in ("status","guard","firstUnknown","checkerSeconds","receipt")}
    conditioned = {}
    for task in ORIGINAL["361"]:
        r = native(job, decimal, task+"-startup")
        if r["startup"] != adoption[task]["conditional"]["startup"]:
            raise ValueError("decimal startup differs from the pilot")
        fingerprints.add(r["checker"]["jvmcontract"])
        conditioned[task] = {k:r[k] for k in ("status","startup","checkerSeconds","receipt")}
    if len(fingerprints) != 1: raise ValueError("comparison spans different native executables")
    primary = Counter()
    for n, case in historical["cases"].items():
        primary.update(original_scope(case, rows.get(n,{})))
    scores = {t:r["status"] for t,r in rows["361"].items()}
    for task in scores:
        if scores[task] == "unresolved" and adoption[task]["original"]["status"] == "refuted":
            scores[task] = "refuted"
    return {"executableSha256":fingerprints.pop(), "ordinary":rows, "decimalCompanions":conditioned,
            "primaryOriginal":dict(primary), "javaParserOriginal":original_scope(historical["reserves"]["360"], rows["360"]),
            "decimalOriginal":dict(Counter(scores.values()))}


def checked_raw(job, folder, rows):
    for row in rows:
        file = job.output(folder/row["raw"])
        raw, = read(file)
        if (sha(file) != row["sha256"] or raw["target"] != row["target"] or raw["verdict"] != row["verdict"]
                or raw["stated"]["gap_mode"] != "strict" or raw["stated"]["checker"]["engine"] != "native"
                or ("guard" in row and raw["assume"] != row["guard"])
                or ("unwind" in row and raw["stated"]["bounds"]["unwind"] != row["unwind"])
                or row.get("matchedExpectation") is False
                or (raw["verdict"] == "verified" and raw["stated"]["vacuity"]["status"] != "non-vacuous")):
            raise ValueError("unqualified native record "+str(file))
        if "replayedInputs" in row and raw["counterexample"]["inputs"] != row["replayedInputs"]:
            raise ValueError("physical replay inputs differ from the native counterexample")
        row["receipt"] = rel(file)


def evidence(job, folder):
    if job.record["status"] != "passed": raise ValueError("incomplete producer job "+job.record["id"])
    file = job.output(folder/"evidence.json")
    return read(file), rel(file)


def report():
    jobs = {k:Job(n) for k,n in IDS.items()}
    audit = {}
    for name, job in jobs.items():
        for path in job.files: job.output(path)
        audit[name] = {"id":job.record["id"], "status":job.record["status"], "outputs":len(job.files),
                       "source":job.record["sourceCommit"], "receipt":rel(job.folder/"result.json")}
    enum = {kind+"-"+side:native(jobs["enumOnly"], "copy-set-separator", kind+"-"+side+"-observed")
            for kind in ("postorder","terminal","preorder","nonempty") for side in ("parent","fix")}
    retry = native(jobs["nonemptyRetry"], "copy-set-nonempty-180", "nonempty-parent-observed")
    first = enum["nonempty-parent"]
    if (first["checker"] != retry["checker"] or first["guard"] != retry["guard"] or first["bounds"] != retry["bounds"]
            or any(r["startup"] != retry["startup"] for r in enum.values())):
        raise ValueError("the retry changed the checker or scope")
    decisions = dict(Counter(r["status"] for r in (enum | {"nonempty-parent":retry}).values()))

    explicit, tables = {}, {}
    for side in ("parent","fix"):
        folder = Path("verification/domain-foundations/separator-inputs")/side
        e, receipt = evidence(jobs["explicitSeparator"], folder)
        if set(e["claims"]) != {"pilot-text","current-text","current-absent","current-postorder"} or len(e["freshJvmControls"]) != 11:
            raise ValueError("incomplete separator comparison")
        checked_raw(jobs["explicitSeparator"], folder, e["claims"].values())
        explicit[side] = {"receipt":receipt, "claims":e["claims"], "freshJvmControls":len(e["freshJvmControls"])}
        for num in ("355","361"):
            folder = Path("verification/domain-foundations/jackson-tables")/num/side
            e, receipt = evidence(jobs["jackson"], folder)
            if (set(e["claims"]) != {"pilot-ascii","frozen-ascii","table-ascii","table-upperByte","frozen-firstFactory","table-firstFactory"}
                    or e["originalJvmAsciiInputs"] != 128 or e["originalJvmInput0x141"] != (10 if num=="355" else -1)):
                raise ValueError("incomplete original Jackson table comparison")
            checked_raw(jobs["jackson"], folder, e["claims"].values())
            tables.setdefault(num,{})[side] = {"receipt":receipt,"classSha256":e["classSha256"],"input0x141":e["originalJvmInput0x141"], "claims":e["claims"]}

    folder = Path("verification/domain-foundations/schema-sets-confirmed")
    schema, receipt = evidence(jobs["schema"], folder)
    if {(s["example"],s["side"]) for s in schema["sites"]} != {(n,s) for n in ("355","361") for s in ("parent","fix")}:
        raise ValueError("missing original Avro site")
    checked_raw(jobs["schema"], folder, schema["claims"])
    for site in schema["sites"]:
        if (site["instructions"] != 56 or site["changedLiteral"] != "refused" or sha(ROOT/site["buildReceipt"]) != site["buildSha256"]
                or site["ordinaryJvmContents"] != "held" or site["originalJvmConstruction"] != "held"):
            raise ValueError("unqualified schema interval")
        checked_raw(jobs["schema"], folder/site["example"]/site["side"], site["constructorClaims"])

    historical = read(ROOT/"verification/organic-java-pr-campaign.json")
    adoption = repeated_decimal()["tasks"]  # revalidates the two original-entry decimal counterexamples
    before = comparison(jobs["beforeTables"], "followup-original", "followup-decimal-startup", historical, adoption)
    final = comparison(jobs["final"], "table-final-original", "table-final-decimal-startup", historical, adoption)
    for side in explicit.values():
        for key, row in side["claims"].items():
            if key.startswith("current-") and row["checkerSha256"] != before["executableSha256"]:
                raise ValueError("separator comparison used another checker")
    for site in schema["sites"]:
        if any(c["checkerSha256"] != before["executableSha256"] for c in site["constructorClaims"]):
            raise ValueError("schema constructor comparison used another checker")
    for family in tables.values():
        for side in family.values():
            if any(c["checkerSha256"] != final["executableSha256"] for k,c in side["claims"].items() if k != "pilot-ascii"):
                raise ValueError("Jackson table comparison used another checker")
    return {"schema":"domain-foundations-followup/v1", "jobs":audit,
            "beforeJacksonTables":before, "final":final,
            "javaParser":{"enumOnly60":enum,"nonemptyRetry":retry,"enumDecisions":decisions,"explicitInputs":explicit},
            "avroSchema":{"receipt":receipt, "producerSha256":schema["producerSha256"],"claims":schema["claims"],"sites":schema["sites"]},
            "jackson":tables}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = json.dumps(report(), indent=2, ensure_ascii=False)+"\n"
    file = DATA/"followup.json"
    if args.check:
        if file.read_text() != result: raise SystemExit("follow-up scorecard differs from the verification receipts")
        print("Domain follow-up matches the collected results")
    else:
        file.write_text(result)
