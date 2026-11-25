"""Register paired resource postconditions on fresh original JVMs and check their physical witnesses."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

import native_resources
from history import ROOT, benchmark, encoded
from scaffold_first import DEST, JDK, compile_java, digest, javaenv, read, save, scratch
from stock_history import classpath

OUT = DEST.parent / "resource-postconditions"
# The Java predicate describes the whole admitted implication, including the intended-change exception.
CLAIMS = [
    ("paired", ["--assume", "true"], "true", "previous == result"),
    ("selected", ["--assume", "selected"], "selected", "previous == result"),
    ("missing", ["--assume", "!selected"], "!selected", "previous == result"),
    ("allowed", ["--assume", "true", "--unchanged-unless", "selected"], "!selected", "previous == result"),
    ("offset", ["--results-agree-when", "(!selected && previous == result) || (selected && previous + 1 == result)"],
        "true", "(!selected && previous == result) || (selected && previous + 1 == result)"),
    ("different-missing", ["--unchanged-unless", "selected", "--results-agree-when", "previous != result"],
        "!selected", "previous != result"),
]


def original_table(scope, work):
    src = work / "OriginalPredicates.java"
    methods = []
    for name, _, domain, relation in CLAIMS:
        methods.append(f'        System.out.println("{name} " + ({domain}) + " " + ({relation}));')
    src.write_text("""public final class OriginalPredicates {
    public static void main(String[] args) {
        boolean selected = Boolean.parseBoolean(args[0]);
        int previous = Integer.parseInt(args[1]), result = Integer.parseInt(args[2]);
""" + "\n".join(methods) + "\n    }\n}\n")
    classes = work / "oracle"
    compile_java([src], classes, [], javaenv())
    results = {name: [] for name, *_ in CLAIMS}
    for n, selected in enumerate(scope["inputs"]):
        old, new = [scope["sides"][side]["observations"][n] for side in ("old", "new")]
        argv = [JDK / "bin/java", "-XX:-UsePerfData", "-cp", classes, "OriginalPredicates",
                str(selected).lower(), str(old), str(new)]
        for line in subprocess.check_output(argv, text=True, env=javaenv()).splitlines():
            name, admitted, relation = line.split()
            results[name].append({"selected": selected, "old": old, "new": new, "admitted": admitted == "true",
                                  "relation": relation == "true"})
    return {"original": scope, "independentOracle": digest(src), "claims":
            [{"name": name, "arguments": args, "domain": domain, "relation": relation, "rows": results[name]}
             for name, args, domain, relation in CLAIMS]}


def check(checker, sides, case, claims, work):
    old, new = sides["old"], sides["new"]
    out = OUT / "measured" / case
    out.mkdir(parents=True, exist_ok=True)
    common = [checker, "equivalence", "--before", old[0], "--after", new[0],
              "--before-classpath", classpath(old[1]), "--classpath", classpath(new[1]),
              "--target", "PairResourceGate#read", "--engine", "native", "--gaps", "strict",
              "--unwind", "16", "--max-array-length", "8", "--timeout", "120", "--json"]
    rows = []
    with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for claim in claims:
            cmd = [*common, *claim["arguments"], "--work", work / ("run-" + claim["name"])]
            raw = benchmark.measure(list(map(str, cmd)), 180)
            answer = benchmark.outcome_of({"kind":"regression"}, raw["stdout"]) or {}
            for field in ("stdout","stderr"):
                archive.writestr(claim["name"] + "/" + field, raw[field])
            archive.writestr(claim["name"] + "/argv.json", encoded(list(map(str,cmd))))
            bad = [r for r in claim["rows"] if r["admitted"] and not r["relation"]]
            verdict = answer.get("verdict")
            if raw["killed"] or answer.get("vacuous") or verdict != ("violation" if bad else "verified"):
                raise ValueError(f'{case} {claim["name"]}: {verdict} {answer.get("problem")}')
            if bad:
                w = answer.get("counterexample") or {}
                hit = next((r for r in bad if (w.get("inputs") or [{}])[0].get("value") is r["selected"]), None)
                if (not hit or w.get("before") != str(hit["old"]) or w.get("after") != str(hit["new"])
                        or answer.get("replay") != {"by":"jvm","reproduced":True}):
                    raise ValueError("unconfirmed original witness for " + claim["name"])
            rows.append({"name":claim["name"],"verdict":verdict,"counterexample":answer.get("counterexample"),
                         "replay":answer.get("replay"),"assumptions":(answer.get("stated") or {}).get("assumptions", []),
                         "wallSeconds":raw["seconds"],"cpuSeconds":raw["cpuSeconds"],"peakMB":raw["peakMB"]})
    save(out / "summary.json", {"job":os.environ.get("VERIFY_JOB_ID"),"source":os.environ.get("VERIFY_SOURCE_COMMIT"),
         "checkerSha256":digest(checker),"registrationSha256":digest(OUT / "registrations" / (case + ".json")),
         "archiveSha256":digest(out / "executions.zip"),"rows":rows})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("register", "measure"))
    p.add_argument("cases", nargs="+", choices=native_resources.NAMES)
    args = p.parse_args()
    for case in args.cases:
        with scratch(prefix="original-resource-relations-") as temporary:
            work = Path(temporary)
            sides, scope = native_resources.build(work, case)
            if scope != read(native_resources.OUT / "registrations" / (case + ".json")):
                raise ValueError("the original deployments or public observations changed")
            registration = original_table(scope, work)
            file = OUT / "registrations" / (case + ".json")
            if args.action == "register":
                save(file, registration)
            else:
                if registration != read(file):
                    raise ValueError("registered public question changed")
                os.environ.update(javaenv())
                check(Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve(),
                      sides, case, registration["claims"], work)
            print(case, args.action, len(registration["claims"]), flush=True)
