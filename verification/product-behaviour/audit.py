"""Import only source-bound collector outputs and independently audit each public plan and receipt."""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from register import HERE, ROOT, manifests, read, upgrade_replay, write
from targets import change_evidence


def require(ok, why):
    if not ok:
        raise ValueError(why)


def collect(collector):
    jobs = []
    outputs_root = (HERE / "results").relative_to(ROOT)
    specs = ROOT / "verification/jobs"
    for spec in sorted(specs.rglob("*.json")):
        doc = read(spec)
        if not any("verification/product-behaviour/" in s["run"] for s in doc.get("steps", [])):
            continue
        result_file = collector / "verification/results" / spec.parent.relative_to(specs) / doc["id"] / "result.json"
        if not result_file.is_file():
            continue
        result = read(result_file)
        require(doc == result["job"]["spec"] and doc["id"] == result["id"] and
                hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest() == result["job"]["sha256"],
                "different collector specification: " + doc["id"])
        outputs = []
        for item in result["outputs"]:
            rel = Path(item["path"])
            require(not rel.is_absolute() and ".." not in rel.parts and rel.is_relative_to(outputs_root)
                    and item["change"] != "deleted", "output outside the study")
            path = ROOT / rel
            digest = item["sha256"]
            if path.exists():
                require(upgrade_replay.sha(path) == digest, "a different experiment owns " + str(rel))
            else:
                candidates = [result_file.parent / "outputs" / rel, collector / rel]
                source = next((f for f in candidates if f.is_file() and upgrade_replay.sha(f) == digest), None)
                require(source is not None, "cannot verify " + str(rel))
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
                    tmp = Path(file.name)
                    with source.open("rb") as original:
                        shutil.copyfileobj(original, file)
                require(upgrade_replay.sha(tmp) == digest, "copy changed during collection")
                tmp.replace(path)
            outputs.append({"path":str(rel), "sha256":digest})
        jobs.append({"id":doc["id"], "status":result["status"], "source":result["sourceCommit"],
                     "specSha256":result["job"]["sha256"], "resultSha256":upgrade_replay.sha(result_file),
                     "usage":result["usage"], "outputs":outputs})
    write(HERE / "jobs.json", jobs)
    return jobs


def plan_without_inventory(archive, name):
    """Read the frozen writer's claim records without expanding millions of unrelated candidate methods."""
    with archive.open(name) as member, io.BufferedReader(member) as stream:
        prefix = bytearray()
        for line in stream:
            if line == b'  "inventory": {\n':
                break
            prefix.extend(line)
        else:
            raise ValueError("missing inventory in " + name)
        # Nested JSON keys are more deeply indented. The frozen writer escapes newlines inside strings.
        boundary = b'\n  },\n  "tools": '
        tail = b""
        while chunk := stream.read(262144):
            block = tail + chunk
            at = block.find(boundary)
            if at >= 0:
                return json.loads(prefix + b'  "tools": ' + block[at+len(boundary):] + stream.read())
            tail = block[-(len(boundary)-1):]
    raise ValueError("incomplete inventory in " + name)


def audit_first(folder, summary_path):
    from qualify import outcomes
    case = read(folder / "case.json")
    physical = read(folder / "physical.json")
    summary = read(summary_path)
    require(summary["bindingsSha256"] == upgrade_replay.sha(folder / "bindings.json")
            and physical["probeSha256"] == upgrade_replay.sha(folder / "UpgradeProbe.java")
            and physical["caseSha256"] == upgrade_replay.sha(folder / "case.json"), "registration differs")
    actual = {(row["side"], row["question"], tuple(row["args"])): {"return":row["return"]}
              for row in physical["observations"]}
    require(len(actual) == physical["freshProcesses"] == 2*sum(len(q["inputs"]) for q in case["questions"]),
            "missing or repeated physical trial")
    packed = summary_path.with_name("plans.zip")
    require(upgrade_replay.sha(packed) == summary["archiveSha256"], "archive digest differs")
    seen, checked = set(), 0
    with zipfile.ZipFile(packed) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), "duplicate archive member")
        for mode, measurement in summary["runs"].items():
            plan = plan_without_inventory(archive,mode + ".json")
            require(plan["executionState"] == "complete" and plan["tools"]["comparator"] == summary["comparatorSha256"],
                    "different public plan")
            binary = plan["deploymentQuestions"]["originalBinary"]
            branches = [(plan["claims"], measurement["claims"])]
            if isinstance(binary, dict):
                branches.append((binary["claims"], measurement["originalBinaryClaims"]))
            for branch, (nodes, rows) in enumerate(branches):
                for node, row in zip(nodes, rows, strict=True):
                    require(all(node.get(k) == row[k] for k in ("claimKey","executionKey","status","children","receipt")),
                            "summary disagrees with archived plan")
                    receipt = node.get("receipt")
                    if not receipt:
                        require(node["status"] == "open", "decided without a public receipt")
                        continue
                    blob = archive.read(receipt["path"])
                    require(hashlib.sha256(blob).hexdigest() == receipt["sha256"], "receipt digest differs")
                    seen.add(receipt["path"])
                    evidence = json.loads(blob)
                    checked += 1
                    if evidence.get("cases") == node["domain"]:
                        recomposed = change_evidence.compose({"entry":node["entry"],"cases":node["domain"]}, evidence, node["intent"])
                        children = [{k:v for k,v in child.items() if k != "id"} for child in node["children"]]
                        require(children == recomposed["children"], "different public evidence on replay")
                        require(node["status"] == "open" or recomposed["status"] == node["status"], "wrong composition")
                        if branch == 0 and mode in ("cold","warm","clean"):
                            for child in children:
                                for side in ("old","new"):
                                    if child[side] is not None:
                                        require(child[side] == actual[side,node["id"],tuple(child["arguments"])],
                                                "qualified result differs from the independent physical trial")
        require(seen == {n for n in archive.namelist() if n.startswith("receipts/")}, "unreferenced or absent evidence")
    runs = summary["runs"]
    for k in ("claims","originalBinaryClaims"):
        require(outcomes(runs["cold"][k]) == outcomes(runs["warm"][k]) == outcomes(runs["clean"][k])
                and outcomes(runs["replacement"][k]) == outcomes(runs["replacement-clean"][k]), "warm and clean differ")
    claims = runs["cold"]["claims"]
    inputs = [c for r in claims for c in (r["children"] or [])]
    return {"case":folder.name,"decisions":{r["id"]:r["status"] for r in claims},
            "physicalJVMs":len(actual),"registeredHistories":len(actual)//2,
            "originalReached":sum(c.get("old") is not None and c.get("new") is not None for c in inputs),
            "differences":sum(c["old"] != c["new"] for c in inputs if c.get("old") is not None and c.get("new") is not None),
            "coldQualifiedEntries":sum(r["freshQualifiedEntries"] for r in claims),
            "warmHits":sum(a["action"] == "exact reuse" for r in runs["warm"]["claims"] for a in (r["execution"] or {}).values()),
            "claimSides":2*len(claims),
            "freshEntriesByRun":{m:sum(r["freshQualifiedEntries"] for r in v["claims"]) for m,v in runs.items()},
            "alternateBinaryFreshEntriesByRun":{m:sum(r["freshQualifiedEntries"] for r in v["originalBinaryClaims"]) for m,v in runs.items()},
            "seconds":{m:v["wallSeconds"] for m,v in runs.items()},"receiptReferences":checked,"uniqueReceipts":len(seen),
            "firstOpenDependencies":{r["id"]: r["reason"] or r["firstOpenDependency"] for r in claims if r["status"] == "open"}}


def audit_checked(folder):
    from checked import check_trace, expected_count
    from predicate_proof import prove
    path = HERE/"results"/folder.name/"checked.json.gz"
    doc = json.loads(gzip.decompress(path.read_bytes()))
    physical = {(r["side"],tuple(r["args"])):{"return":r["return"]} for r in read(folder/"physical.json")["observations"]}
    graphs = manifests(folder)
    require(doc["coldArchiveSha256"] == upgrade_replay.sha(path.parent/"first/plans.zip"), "different cold plan")
    for side, proof in doc["proofs"].items():
        require(prove(folder.name,Path(graphs[side]["classpath"][0]["file"]),side) == proof, "different original method proof")
    seen = set()
    applied = 0
    for trial in doc["trials"]:
        side,args = trial["side"],trial["args"]
        reference = physical[side,tuple(args)]
        seen.add((side,tuple(args)))
        proof = doc["proofs"][side]
        for mode,name in (("original","untouched"),("apply","substituted")):
            repeats = trial[name]
            require(len(repeats) == 2 and repeats[0] == repeats[1], "different or missing live repeat")
            for rep in repeats:
                require(rep["public"] == reference and rep["proof"] == proof["key"], "different public result or proof key")
                check_trace(folder.name,args,side,mode,proof,Path(graphs[side]["classpath"][0]["file"]),rep["events"],reference)
                if mode == "apply": applied += len(rep["events"])
        require([e[1:] for e in trial["untouched"][0]["events"]] == [e[1:] for e in trial["substituted"][0]["events"]],
                "different live arguments or effects")
    require(seen == set(physical) and len(seen) == len(doc["trials"]), "incomplete checked domain")
    omitted = {(r["side"],tuple(r["args"])) for r in doc["controls"] if r.get("withheldApplication") == "refused"}
    require(omitted == {k for k in physical if expected_count(folder.name,list(k[1]))} and
            {r["side"] for r in doc["controls"] if r.get("staleCode") == "refused"} == {"old","new"}, "missing negative controls")
    return {"originalHistories":2*len(seen),"substitutedHistories":2*len(seen),"applications":applied,
            "omittedApplications":len(omitted),"staleMethods":2,"sha256":upgrade_replay.sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", type=Path, help="collector checkout containing the official results")
    parser.add_argument("--write", action="store_true", help="write the audited campaign index")
    args = parser.parse_args()
    jobs = collect(args.collect.resolve()) if args.collect else read(HERE / "jobs.json")
    for job in jobs:
        for output in job["outputs"]:
            require(upgrade_replay.sha(ROOT/output["path"]) == output["sha256"], "recorded output differs")
    records = [audit_first(HERE/"cases"/p.parents[1].name,p) for p in sorted((HERE/"results").glob("*/first/summary.json"))]
    checked = {p.parent.name:audit_checked(HERE/"cases"/p.parent.name) for p in sorted((HERE/"results").glob("*/checked.json.gz"))}
    result = {"jobs":dict(Counter(j["status"] for j in jobs)), "outputDigests":sum(len(j["outputs"]) for j in jobs),
              "cases":records,"checkedContinuations":checked}
    if args.write:
        write(HERE/"audit.json",result)
    elif (HERE/"audit.json").exists():
        require(result == read(HERE/"audit.json"), "campaign index differs")
    print(len(records),"first frozen plans,",result["jobs"],result["outputDigests"],"output digests,",
          sum(r["receiptReferences"] for r in records),"public receipt references verified")


if __name__ == "__main__":
    main()
