"""Replay a case-specific checked summary in its original public caller and check its contribution."""
import argparse
import contextlib
import gzip
import json
from pathlib import Path
import sys
import tempfile

from register import HERE, ROOT, manifests, read, upgrade_replay
sys.path.insert(0, str(ROOT / "lib/benchmark/organic-composition"))
from live import compile_tracer, frozen_cold, member_site, observe
from predicate_proof import prove, require


def expected_count(case, args):
    if case == "J02":
        return 0 if args == ["br"] else 2
    if case == "J01":
        return 0 if args == ["markup"] else 2
    return 8 if args == ["directory"] else 6


def check_trace(case, args, side, mode, proof, jar, events, expected):
    require(len(events) == expected_count(case, args), "missing selected application")
    for event in events:
        require(event[0] == ("original" if mode == "original" else "applied"), "wrong application mode")
        target = member_site(jar, event[-4:])
        if case == "J02":
            _, name, options, mask, result, inherits = event[:-4]
            require(target["owner"] == proof["owner"] and target["name"] == "isEmpty" and name == args[0]
                    and mask == "2" and (int(options) & int(mask) != 0) == (result == "true")
                    and (inherits == "true") == (side == "new"), "different tag provenance")
        elif case == "J01":
            _, literal, before, after = event[:-4]
            require(target["owner"] == "org.commonmark.node.Visitor" and target["name"] == "visit"
                    and target["descriptor"] == "(Lorg/commonmark/node/Code;)V"
                    and after == (before + literal if side == "new" else before), "wrong visitor effect")
        else:
            _, name, key, dest, matched = event[:-4]
            decision = name.startswith(key) if side == "old" else (name == key or (key.endswith("/") and name.startswith(key)))
            require(target["owner"] == proof["owner"] and target["name"] == proof["method"]
                    and decision == (matched == "true") and dest in ("dog", "dog/", "hound", "hound/"), "wrong rename decision")
    if case == "J02" and events:
        pop = events[0][4] == "true"
        require(("/body//" in expected["return"]) == pop, "original tree does not consume the checked branch")
    if case == "J01" and events:
        require([row[1] for row in events] == [("foo" if args == ["mixed"] else "x & y"), "edit & again"],
                "wrong original AST edit")
    if case == "J06" and args == ["neighbor"]:
        require(any(row[1:3] == ["catalog","cat"] and (row[4] == "true") == (side == "old") for row in events),
                "missing the observed file/prefix discriminator")


def capture(case, folder, classes, jars, entry, args, side, mode, proof, expected, stale=False):
    with tempfile.TemporaryDirectory(prefix="product-summary-trial-") as temporary:
        temp = Path(temporary)
        props = {"public":entry, "side":side, "mode":mode, "code":("0"*64 if stale else proof["code"]),
                 "pool":proof["pool"], "owner":proof["owner"], "input":args[0]}
        for k in ("exit","consumerOffset","rejectReturn"):
            if k in proof: props[k] = proof[k]
        if "returns" in proof: props["returns"] = ",".join(map(str,proof["returns"]))
        config = temp / "case.properties"
        config.write_text("".join(f"{k}={v}\n" for k,v in props.items()))
        with contextlib.chdir(temp):
            value, events, invocation, origins = observe(classes,jars,entry,args,temp/"vm",config)
        require(value == expected, f"{case}/{side}/{args}: different public observation")
        require(origins.get(entry.split("#")[0]) == {jars[0]} and origins.get(proof["owner"]) == {jars[0]},
                "different original caller or helper deployment")
        check_trace(case,args,side,mode,proof,jars[0],events,value)
        return {"public": value, "invocation": invocation, "events":events, "proof":proof["key"]}


def run(case, case_root, archive_root, probe):
    folder = case_root / case
    doc = read(folder/"case.json")
    graphs = manifests(folder)
    archive = archive_root / case / "first/plans.zip"
    cold = frozen_cold(archive)
    predicted = {(tuple(c["arguments"]),side):c[side] for node in cold["claims"] for c in node["children"]
                 for side in ("old","new") if c["status"] == "established"}
    original_cases = [item["args"] for q in doc["questions"] for item in q["inputs"]]
    require(len(predicted) == 2*len(original_cases), "complete original public plans required")
    results = {"case":case,"coldArchiveSha256":upgrade_replay.sha(archive),"proofs":{},"trials":[],"controls":[]}
    with tempfile.TemporaryDirectory(prefix="product-summary-") as temporary:
        work = Path(temporary)
        for side, graph in graphs.items():
            if probe and side != probe[0]: continue
            jars = [Path(row["file"]) for row in graph["classpath"]]
            proof = prove(case,jars[0],side)
            results["proofs"][side] = proof
            build = work / side
            build.mkdir()
            classes, sources = compile_tracer(folder,build,jars)
            results["tracer"] = sources
            for args in original_cases:
                if probe and args != [probe[1]]: continue
                expected = predicted[tuple(args),side]
                def replay(mode, stale=False):
                    return capture(case,folder,classes,jars,doc["entry"],args,side,mode,proof,expected,stale)
                if probe:
                    result = replay("apply")
                    print(case,side,args, result["public"],len(result["events"]), "checked applications")
                    return
                untouched = [replay("original") for _ in range(2)]
                applied = [replay("apply") for _ in range(2)]
                require(untouched[0] == untouched[1] and applied[0] == applied[1] and
                        [e[1:] for e in untouched[0]["events"]] == [e[1:] for e in applied[0]["events"]],
                        "different runtime operands, effects or call sites")
                results["trials"].append({"side":side,"args":args,"untouched":untouched,"substituted":applied})
                if applied[0]["events"]:
                    try:
                        check_trace(case,args,side,"apply",proof,jars[0],applied[0]["events"][:-1],expected)
                    except ValueError as exc:
                        require(str(exc) == "missing selected application", "unexpected missing-premise reason")
                        results["controls"].append({"side":side,"args":args,"withheldApplication":"refused","public":expected})
                    else: raise ValueError("accepted an omitted application")
            if not probe:
                args = next(a for a in original_cases if expected_count(case,a))
                try:
                    capture(case,folder,classes,jars,doc["entry"],args,side,"apply",proof,predicted[tuple(args),side],stale=True)
                except ValueError as exc:
                    require("stale" in str(exc), "wrong stale-proof refusal: " + str(exc))
                    results["controls"].append({"side":side,"staleCode":"refused","reason":str(exc)})
                else: raise ValueError("accepted a stale method")
    if probe: raise ValueError("unknown probe history")
    path = HERE/"results"/case/"checked.json.gz"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(results,sort_keys=True).encode(),mtime=0))
    count = sum(len(r["events"]) for trial in results["trials"] for r in trial["substituted"])
    print(case,len(results["trials"]),"input/deployment pairs,",count,"actual substitutions,",len(results["controls"]),"refusals")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",choices=["J01","J02","J06"])
    parser.add_argument("--probe",nargs=2,metavar=("SIDE","INPUT"))
    parser.add_argument("--case-root",type=Path,default=HERE/"cases")
    parser.add_argument("--archive-root",type=Path,default=HERE/"results")
    args=parser.parse_args()
    run(args.case,args.case_root.resolve(),args.archive_root.resolve(),args.probe)
