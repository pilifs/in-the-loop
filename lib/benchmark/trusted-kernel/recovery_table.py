"""Build the recovery comparison from managed job outputs, checking the collector's digests."""
import argparse
from functools import cache
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KERNEL = Path("verification/kernel-recovery")
RECEIVER = Path("verification/receiver-discovery")
LRAT = Path("verification/trusted-kernel-recovery/lrat")
sys.path.insert(0, str(ROOT / "verification"))
import layout

JOBS = {
    "historical": "20261124-034953-audit-historical-induction-queries-again",
    "adapter": "20261124-043151-compare-the-three-pinned-guava-controls",
    "ranges": "20261124-034953-qualify-long-range-fill-and-portable-gua",
    "fastutil": "20261124-035044-qualify-both-fastutil-range-fill-loops-o",
    "lean": "20261124-043143-check-the-executed-jdk-range-branches-an",
    "reverse": "20261124-041759-bind-the-commons-lang-reversal-theorem-t",
    "pilot": "20261124-034954-check-five-original-array-contracts-thro",
    "core": "20261124-043118-certify-the-ordinary-guava-verdict-and-h",
    "extensions": "20261124-043118-check-jackson-and-utf-16-ordinary-sat-ev",
    "configuration": "20261124-035245-recover-json-and-yaml-public-callers-fro",
    "installed-opening": "20261124-034422-check-replacement-properties-identity-an",
    "split": "20261124-041856-replay-the-configuration-callers-past-th",
    "installed": "20261124-043349-qualify-live-parent-removal-through-the",
    "parser": "20261124-041236-replay-javaparser-separator-claims-on-th",
    "parser-opening": "20261123-230231-check-javaparser-traversal-in-fresh-sepa",
    "xz-opening": "20261123-231925-repeat-xz-cache-profiles-from-the-digest",
    "xz-profiles": "20261124-035617-retry-xz-frame-and-cache-roots-beyond-bo",
    "xz": "20261124-041236-replay-the-original-xz-frame-and-cache-w",
}
SEARCH = "Every non-null, allocated primitive array of legal Java length and each scalar value of its Java type."
FILL = "Allocated non-null array, arbitrary entry cells and value, signed indices 0 <= from <= to <= length."
ENVIRONMENT = "Single-threaded JVM, verified successfully initialized classes, pinned resolution and sufficient resources."
BENCHMARK = "python3 -B lib/benchmark/trusted-kernel/"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def comparison(root):
    root = root.resolve()
    jobs, inputs, rows = {}, {}, []

    @cache
    def receipt(group):
        job = JOBS[group]
        folder = layout.find_result(root, job)
        if folder is None:
            raise ValueError("missing managed receipt for " + job)
        path = (folder / "result.json").relative_to(root)
        data = json.loads((root / path).read_bytes())
        if data["id"] != job or data["status"] != "passed":
            raise ValueError("missing managed pass for " + job)
        spec = data["job"]["spec"]
        if hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest() != data["job"]["sha256"]:
            raise ValueError("job specification digest differs: " + job)
        jobs[job] = {"receipt": str(path), "sha256": sha(root / path), "sourceCommit": data["sourceCommit"],
                     "steps": [s["run"] for s in spec["steps"]], "summary": data["summary"]}
        return {o["path"]: o["sha256"] for o in data["outputs"] if o.get("sha256")}

    def read(group, path):
        pin = receipt(group).get(str(path))
        if not pin or sha(root / path) != pin:
            raise ValueError(f"{path} differs from the output of {JOBS[group]}")
        inputs[str(path)] = {"sha256": pin, "job": JOBS[group]}
        return json.loads((root / path).read_bytes())

    def add(key, opening, final, route, scope, subject, checker, reason, path, transfer, replay=None):
        rows.append({"key": key, "opening": opening, "final": final, "route": route, "scope": scope,
                     "subject": subject, "checker": checker, "firstDecision": reason, "evidence": str(path),
                     "reuse": transfer, "replay": {"command": replay} if replay else {"job": inputs[str(path)]["job"]}})

    hpath = KERNEL / "historical.json"
    historical = read("historical", hpath)
    apath = KERNEL / "historical-adapter.json"
    comparisons = {r["key"]: r for r in read("adapter", apath)["cases"]}
    for r in historical["cases"]:
        key = r["key"]
        ordinary = comparisons[key]
        if ordinary["record"]["certificateSha256"] != r["genuine"]["smtSha256"]:
            raise ValueError("independent ordinary preparation differs for " + key)
        reason = {"genuine": r["genuine"]["producer"], "smtSha256": r["genuine"]["smtSha256"],
                  "rust": r["independent"], "jvm": r["jvm"], "comparisonEvidence": str(apath),
                  "comparisonWithoutRecord": ordinary["withoutStoredRecord"]["repeated"],
                  "comparisonWithPristine": ordinary["withPristineRecord"]["repeated"]}
        reason.update({name: r[name] for name in ("historicalFault", "omittedExitControl", "missingHintControl") if name in r})
        add(key, r["genuine"]["producer"], r["independent"]["result"], "Historical Python/Z3 and independent Rust",
            SEARCH, {"class": r["classSha256"], "superclass": r["supportSha256"], "request": r["requestSha256"]},
            {"rust": historical["checkerSha256"], "z3": r["genuine"]["solver"]["sha256"]}, reason, hpath,
            "Frozen checker, regenerated untrusted hints. The miss ablation is a query-inventory trial.")

    jpath = KERNEL / "range-jdk.json"
    for key, r in read("ranges", jpath)["cases"].items():
        if "after" in r:
            result = r["after"]
            opening = r["before"]["stdout"]
            transfer = "JDK long width and local 5, full 64-bit store"
            scope = FILL
        elif "result" in r:
            result = r["result"]
            opening = r["oldCertificate"]["stdout"]
            transfer = "Existing Guava first-match rule with a fresh request for the deployed class and dependency"
            scope = SEARCH
        else:
            continue  # The fastutil release row below includes both pre-edit refusals.
        add(key, opening, "established", "Independent Rust", scope,
            {"class": r["classSha256"], "jar": r.get("jarSha256"), "dependencies": r["supportSha256"],
             "request": r["requestSha256"]},
            result["checkerSha256"], result["stdout"], jpath, transfer)
    fpath = KERNEL / "fastutil.json"
    f = read("fastutil", fpath)
    add(f["key"], "unsupported range-fill descriptors, then unsupported external guard binding",
        "established", "Independent Rust", FILL,
        {"jar": f["jarSha256"], "class": f["classSha256"], "guard": f["supportSha256"], "request": f["requestSha256"]},
        f["after"]["checkerSha256"], f["after"]["stdout"], fpath, "External bounds guard and two loop directions")

    for entry in read("pilot", KERNEL / "pilot/summary.json")["cases"]:
        path = KERNEL / "pilot" / entry["receipt"]
        r = read("pilot", path)
        add(entry["key"], entry["ordinary"], r["assurance"], "Ordinary array contract with opt-in Rust",
            r["ordinary"]["domain"] + (" " + r["ordinary"]["caller"]["roots"] if "caller" in r["ordinary"] else ""),
            {"classes": entry["classes"], "request": r["requestSha256"]}, r["independent"]["checkerSha256"],
            {"consumer": r["independent"]["stdout"], "timesSeconds": r["times"]}, path, "Frozen int-range consumer",
            f"python3 examples/tools/build.py {r['example']} --array-induction {r['contract']} --second-opinion")
    path = KERNEL / "pilot/callee-only-for-caller.json"
    r = read("pilot", path)
    add("337/caller-any-length/callee-only", r["ordinary"]["status"], r["assurance"], "Independent Rust",
        FILL + " Caller may alias both roots.", r["deployment"]["classes"], r["independent"]["checkerSha256"],
        r["independent"]["stdout"], path, "Caller owns a separate request for both classes")

    path = KERNEL / "lean.json"
    lean = read("lean", path)
    for key, decision in [("range-branches", lean["counts"]), *lean["edges"].items()]:
        add("lean/" + key, "planning preflight", "checked correspondence", "Lean 4.36.0",
            lean["environment"], {"class": lean["classSha256"], "exporter": lean["compiler"]["binarySha256"]},
            lean["leanExecutable"], decision, path, "Compiled Rust phase decisions and two real forward bodies")
    path = KERNEL / "reverse.json"
    reverse = read("reverse", path)
    for suffix, route, scope, answer, reason, checker in [
        ("valid", "Lean 4.36.0", "Every non-null allocated int array, 0 <= lo <= hi <= length, including empty and singleton ranges.", "established in the byte-bound model",
         reverse["validRange"], reverse["lean"]["sha256"]),
        ("all-signed-bounds", "Original JVM", "All signed bounds including Integer.MIN_VALUE",
         "refuted", reverse["allSignedBounds"], "Temurin 21.0.13+9, observer " + reverse["jvm"]["observerSha256"]),
    ]:
        add(reverse["key"] + "/" + suffix, reverse["frozenRust"]["stdout"], answer, route, scope,
            reverse["classes"], checker, reason, path, "Two cursors and a relation to the entry heap")

    for group in ("core", "extensions"):
        base = LRAT / group
        summary = read(group, base / "summary.json")
        for row in summary["workloads"]:
            key = row["key"]
            directory = base / key.split("/", 1)[1]
            path = directory / "assurance.json"
            a = read(group, path)
            req = read(group, directory / "request.json")
            if a != row["assurance"] or a["status"] != "checked":
                raise ValueError("uncertified workload " + key)
            add(key, row["qualified"], a["ordinary"] + ", complete SAT accounting",
                "Ordinary native with complete SAT accounting",
                "The original bounded request, assumptions and bounds in " + str(directory / "request.json"),
                {"request": a["requestSha256"], "boundary": a["boundarySha256"], "run": req["run"], "bindings": req["bindings"]},
                {"lrat": a["checkerSha256"], "native": req.get("checkerSha256") or req["checker"]["jvmcontract"]},
                {"passes": a["passes"], "satModelsChecked": a["satModelsChecked"], "bundleBytes": a["bundleBytes"]},
                path, "Pinned LRAT checker for UNSAT and clause evaluation for SAT",
                BENCHMARK + "verdict_qualification.py --group core --output OUT" if key.startswith("held/") else
                "python3 examples/tools/build.py " + key.replace("/", " --task ", 1) + " --certify-lrat")
        if group == "core":
            guava = read("core", base / "first-8-release/assurance.json")
            for control in summary["controls"]:
                target = read("core", base / "prefix-sums/assurance.json") if control["control"] == "different-top-level-request" else guava
                add("336/first-8-release/" + control["control"], "ordinary verdict established", control["status"],
                    "Fresh SAT evidence checker", "Complete Guava bundle challenged at one evidence or request binding",
                    {"request": target["requestSha256"], "boundary": target["boundarySha256"],
                     "sourceBundleRequest": guava["requestSha256"]},
                    guava["checkerSha256"], control["reason"], base / "summary.json",
                    "Independently retained request and solver-call inventory")
    for case in ("commons-configuration-565", "commons-configuration-601"):
        path = RECEIVER / "recovery" / case / "measurement.json"
        cfg = read("configuration", path)
        for side, r in cfg["sides"].items():
            primary = cfg["registered"]["sides"][side]
            add(case + "/" + side, "unresolved at the properties read", r["ordinary"]["status"], "Original JVM",
                cfg["scope"], {"source": r["commit"], "classes": r["classBindings"], "classpath": r["classpath"]},
                {"jdk": cfg["jdk"], "native": cfg["checkerSha256"]},
                {"witness": r["ordinary"]["witness"], "native": primary["firstOutstanding"],
                 "observations": [c["expected"] for c in cfg["cases"]], "trees": r["trees"]["jvmBothReadOrders"]},
                path, "Same live-table discriminator on JSON and YAML")
        before = read("installed-opening", RECEIVER / "recovery/installed-properties" / (case + ".json"))
        path = RECEIVER / "recovery/parsed-property" / (case + ".json")
        after = read("split", path)
        for side, results in after["rows"].items():
            for name, r in results.items():
                old = before["rows"][side].get(name)
                add(f"{case}/{side}/installed/{name}", old["native"]["problem"] if old else "new fixed prestate",
                    r["native"]["verdict"], "Strict native with an explicitly installed table",
                    "Four registered selectors and the table installed by the named profile",
                    after["bindings"][side], after["checkerSha256"], r["native"]["problem"] or r["jvm"],
                    path, "The real lookup-name delimiter and the original package initializer")
    path = RECEIVER / "recovery/live-table.json"
    table = read("configuration", path)
    add("jdk-21/live-properties", "setup observation", "reproduced", "Original JVM",
        table["prestate"], {"observer": table["observerClassSha256"], "initializer": table["initializerClassSha256"]},
        table["jdk"], table["observations"], path, "Same installed table, distinct equal Strings and live defaults",
        "python3 -B lib/benchmark/receiver-discovery/recovery.py live")
    path = RECEIVER / "recovery/removed-property/controls.json"
    installed = read("installed", path)
    previous = read("installed-opening", RECEIVER / "recovery/installed-properties/controls.json")
    for name, r in installed["rows"]["control"].items():
        native = r["native"]
        add("jdk-21/installed-properties/" + name, previous["rows"]["control"][name]["native"]["verdict"], native["verdict"],
            "Strict native and original JVM", "Single-threaded process, prestate selected by the named method",
            native["target"], {"native": installed["checkerSha256"], "jdk": installed["jdk"]},
            {"jvm": r["jvm"], "problem": native["problem"], "witness": native["counterexample"]},
            path, "Shared reference and membership through replacement, defaults and parent removal")
    path = RECEIVER / "recovery/javaparser/clean-ordinary/measurement.json"
    parser = read("parser", path)
    for side, requests in parser["sides"].items():
        for name, row in requests.items():
            native = row["native"]
            add(f"javaparser-4538/{side}/{name}", "violation" if side == "parent" and name in ("postorder", "terminal") else "unverifiable",
                native["verdict"], "Ordinary strict native", native["assume"], row["entryClassSha256"],
                parser["checkerSha256"], native["counterexample"] or native["problem"], path,
                "Original caller and process startup; fixed separator runs have separate receipts")
    before = read("parser-opening", RECEIVER / "transfer/javaparser/measurement.json")
    path = RECEIVER / "recovery/javaparser/clean-profiles/measurement.json"
    profiles = read("parser", path)
    for side, subjects in profiles["sides"].items():
        binding = {"class": subjects["boundClassSha256"], "classpath": subjects["classpath"]}
        for name, prof in subjects["profiles"].items():
            native = prof["native"]
            add(f"javaparser-4538/{side}/profile/{name}", before["sides"][side]["profiles"][name]["native"]["verdict"],
                native["verdict"], "Strict native and original JVM",
                f"{prof['key']} = {prof['value']!r} before first use. " + str(native.get("assume") or ""),
                binding, profiles["checkerSha256"], native.get("counterexample") or native.get("problem") or native["target"],
                path, "Fixed separator and repeated initialization controls")
        for name, native in subjects["boundedNonNullSeparator"].items():
            add(f"javaparser-4538/{side}/bounded-separator/{name}", before["sides"][side]["boundedNonNullSeparator"][name]["verdict"],
                native["verdict"], "Strict native", "Every non-null UTF-16 separator of length at most two",
                binding, profiles["checkerSha256"], native.get("counterexample") or native.get("problem") or native["target"],
                path, "Symbolic separator under the named length bound")
    path = RECEIVER / "recovery/xz/clean-witnesses/measurement.json"
    witnesses = read("xz", path)
    for side, group in witnesses["sides"].items():
        row = group["frame"]
        selected = row["attempts"][row["witnessPrestate"]]
        add("commons-compress-767/" + side + "/frame", "refuted in admitted nondefault prestate", row["disposition"],
            "Original JVM", "Four frame selectors, admitting an independently set cache property on first use",
            row["originalClassSha256"], witnesses["checkerSha256"],
            {"input": selected["input"], "setting": selected["value"], "jvm": selected["originalJvm"]}, path,
            "Confirms the earlier witness in an independently prepared source tree")
    path = RECEIVER / "recovery/xz/constructor-progress/measurement.json"
    fixed = read("xz-profiles", path)
    before = read("xz-opening", RECEIVER / "transfer/xz/measurement.json")
    for side, r in fixed["sides"].items():
        for name, prof in r["profiles"].items():
            answer = prof["native"]
            add(f"commons-compress-767/{side}/{name}", before["sides"][side]["profiles"][name]["native"]["verdict"],
                answer["verdict"], "Strict native",
                "The named fixed cache prestate. " + str(answer.get("assume") or ""), r["boundClassSha256"],
                fixed["checkerSha256"], answer.get("problem") or answer.get("proof"), path,
                "Execute initialized cache and both JDK constructors on the same release graph")
    if len({row["key"] for row in rows}) != len(rows):
        raise ValueError("duplicate recovery request")
    return {"schema": "trusted-kernel-receiver-comparison/v1", "semanticEnvironment": ENVIRONMENT,
            "jobs": jobs, "inputs": inputs, "requests": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="checkout with collected job outputs")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = comparison(args.root)
    path = ROOT / KERNEL / "comparison.json"
    if args.check:
        if json.loads(path.read_bytes()) != result:
            raise SystemExit("recovery comparison differs")
        print(f"{len(result['requests'])} request rows bound to {len(result['jobs'])} managed jobs")
    else:
        print(json.dumps(result, indent=2))
