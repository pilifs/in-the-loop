"""Import only source-bound collector outputs and independently audit each public plan and receipt."""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

from register import HERE, ROOT, manifests, read, upgrade_replay
from targets import change_evidence


def require(ok, why):
    if not ok:
        raise ValueError(why)


def collect(collector):
    jobs = []
    outputs_root = (HERE / "results").relative_to(ROOT)
    specs = ROOT / "verification/jobs"
    ledger = HERE/"jobs.json"
    previous = {job["id"]:job for job in read(ledger)} if ledger.is_file() else {}
    for spec in sorted(specs.rglob("*.json")):
        doc = read(spec)
        if not any("verification/product-behaviour/" in s["run"] for s in doc.get("steps", [])):
            continue
        result_file = collector / "verification/results" / spec.parent.relative_to(specs) / doc["id"] / "result.json"
        old = previous.pop(doc["id"], None)
        spec_digest = hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
        if not result_file.is_file():
            if old:
                require(old["specSha256"] == spec_digest and all(upgrade_replay.sha(ROOT/r["path"]) == r["sha256"]
                        for r in old["outputs"]), "earlier result no longer matches its inputs or outputs")
                jobs.append(old)
            continue
        result = read(result_file)
        result_digest = upgrade_replay.sha(result_file)
        require(not old or old["resultSha256"] == result_digest, "an earlier collector result differs: " + doc["id"])
        require(doc == result["job"]["spec"] and doc["id"] == result["id"] and
                spec_digest == result["job"]["sha256"],
                "different collector specification: " + doc["id"])
        outputs = []
        cases = set()
        for item in result["outputs"]:
            rel = Path(item["path"])
            require(not rel.is_absolute() and ".." not in rel.parts and rel.is_relative_to(outputs_root)
                    and item["change"] != "deleted", "output outside the study")
            case = rel.relative_to(outputs_root).parts[0]
            if (HERE/"cases"/case).is_dir():
                cases.add(case)
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
        registrations = {}
        for case in sorted(cases):
            registrations[case] = {}
            for name in ("case.json","bindings.json","UpgradeProbe.java","physical.json"):
                file = HERE/"cases"/case/name
                blob = subprocess.check_output(["git","cat-file","blob",result["sourceCommit"]+":"+str(file.relative_to(ROOT))],cwd=ROOT)
                checksum = hashlib.sha256(blob).hexdigest()
                require(checksum == upgrade_replay.sha(file), f"{doc['id']} ran on a different {case}/{name}")
                registrations[case][name] = checksum
        jobs.append({"id":doc["id"], "status":result["status"], "source":result["sourceCommit"],
                     "specSha256":spec_digest, "resultSha256":result_digest,
                     "usage":result["usage"], "outputs":outputs,"registrations":registrations})
    require(not previous, "an earlier result has lost its job specification")
    change_evidence.write_json(ledger, jobs)
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
    freeze = read(ROOT/"lib/benchmark/organic-composition/freeze.json")
    require(summary["frozenSource"] == freeze["source"] and summary["comparatorSha256"] == freeze["checkerSha256"],
            "original experiment used a different freeze")
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
                    require(all(node.get(k) == row[k] for k in ("claimKey","executionKey","status","children","execution","receipt")),
                            "summary disagrees with archived plan")
                    receipt = node.get("receipt")
                    if not receipt:
                        require(node["status"] == "open", "decided without a public receipt")
                        require(row["freshQualifiedEntries"] == row["reusedQualifiedEntries"] == 0, "entries claimed without receipts")
                        continue
                    blob = archive.read(receipt["path"])
                    require(hashlib.sha256(blob).hexdigest() == receipt["sha256"], "receipt digest differs")
                    seen.add(receipt["path"])
                    evidence = json.loads(blob)
                    actions = row["execution"] or {}
                    counts = Counter()
                    for side, binding in evidence.get("sides", {}).items():
                        reused = actions.get(side, {}).get("action") == "exact reuse"
                        counts[reused] += sum(t["qualifiedMethodEntries"] for t in binding.get("trials",[]))
                    require((counts[False], counts[True]) == (row["freshQualifiedEntries"],row["reusedQualifiedEntries"]),
                            "wrong fresh or reused entry count")
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


def audit_release_pair(folder, path):
    from register import SETUP
    from release_pairs import accumulator
    record = json.loads(gzip.decompress(path.read_bytes()))
    require(record["registeredCaseSha256"] == upgrade_replay.sha(folder/"case.json")
            and record["releaseGraphSha256"] == upgrade_replay.sha(folder/"releases.json")
            and record["originalGraphSha256"] == upgrade_replay.sha(folder/"bindings.json"), "different comparison inputs")
    physical = {(r["side"],tuple(r["args"])):r["return"] for r in read(folder/"physical.json")["observations"]}
    histories, identities = 0, {}
    for kind, graphs in (("release",read(folder/"releases.json")),("pr",read(folder/"bindings.json"))):
        for side, graph in graphs.items():
            key = kind+"-"+side
            data = record["graphs"][key]
            require(data["productionJar"] == graph["classpath"][0]["sha256"], "different subject jar")
            seen = set()
            for r in data["inputs"]:
                args = tuple(r["args"])
                require(physical[side,args] == r["observation"] and args not in seen, "wrong original comparison")
                seen.add(args)
                if folder.name == "J12":
                    program = r["generatedAccumulator"]
                    require(accumulator(program["java"],args[0],side) == program, "different generated field binding")
                else:
                    with zipfile.ZipFile(SETUP/graph["classpath"][0]["file"]) as jar:
                        digest = hashlib.sha256(jar.read("org/sqlite/native/Linux/x86_64/libsqlitejdbc.so")).hexdigest()
                    require(r["mappedNativeSha256"] == digest, "different original JNI image")
                    identities[key] = digest
            require(seen == {args for s,args in physical if s == side}, "incomplete deployment domain")
            histories += len(seen)
    return {"histories":histories,"generatedPrograms":histories if folder.name == "J12" else 0,
            "nativeImages":identities,"sha256":upgrade_replay.sha(path)}


def audit_order(path):
    from maven_order import METHOD, SIG, member_site
    folder = HERE/"cases/J13"
    doc = json.loads(gzip.decompress(path.read_bytes()))
    graphs = manifests(folder)
    expected = {(r["side"],tuple(r["args"])):r["return"] for r in read(folder/"physical.json")["observations"]}
    require(doc["originalPlans"] == upgrade_replay.sha(path.parent/"first/plans.zip")
            and {r["side"] for r in doc["controls"] if "stale parsed-version shape" in r["wrongOperandShape"]} == {"old","new"},
            "wrong Maven plan or missing stale-operand refusals")
    counts,seen = Counter(),set()
    for t in doc["trials"]:
        side,args = t["side"],tuple(t["args"])
        table = doc["proofs"][side]
        require(len(table["returns"]) == 13 and table["jar"] == graphs[side]["classpath"][0]["sha256"]
                and table["checkedReference"] == upgrade_replay.sha(folder/"OrderTable.java"), "different finite table")
        originals,substitutions = t["originals"],t["substitutions"]
        require(len(originals) == len(substitutions) == 2 and originals[0] == originals[1] == substitutions[0] == substitutions[1],
                "original and substituted comparison histories differ")
        seen.add((side,args))
        for r in substitutions:
            require(r["value"] == {"return":expected[side,args]}, "wrong observed range")
            for e in r["events"]:
                if e[0] == "public-match":
                    counts["matchVersion"] += 1
                    continue
                target = member_site(Path(graphs[side]["classpath"][0]["file"]),e[-4:])
                require(e[0] == "compare" and (target["owner"], target["name"], target["descriptor"]) == (METHOD,"compareTo",SIG)
                        and table["returns"][e[2]+"/"+e[4]] == int(e[6]) and
                        (table["shapes"][e[2]],table["shapes"][e[4]]) == (e[3],e[5]), "unbound comparator use")
                counts[e[1]] += 1
    require(seen == set(expected) and len(doc["trials"]) == len(seen), "missing range histories")
    return {"substitutedHistories":2*len(seen),"events":dict(counts),"sha256":upgrade_replay.sha(path)}


def audit_transfers(path):
    from transfer_controls import axes, weeks
    data = read(path)
    for case, checksum in data["frozenSummaries"].items():
        require(upgrade_replay.sha(HERE/"results"/case/"first/summary.json") == checksum, "different frozen transfer record")
    require(axes() == data["axes"] and weeks() == data["defaultWeeks"], "different axis or locale transfer")
    require(all(a["action"] == "exact reuse" for a in data["untouchedHyperlinks"]["warm"].values()), "untouched link cache missed")
    for side in ("old","new"):
        for kind in ("ordinary","abstract"):
            stream = data["kryo"][side+"-"+kind]
            require(stream["writes"] == stream["reads"] and int(stream["reads"][-1][1]) == stream["completeBytes"],
                    "different complete Kryo prefix")
            require(stream["completeBytes"] <= stream["streamBytes"] and bool(stream["failure"]) == (side == "old" and kind == "abstract"),
                    "wrong abstract-token outcome")
        kinds = data["kryo"][side+"-enum-kinds"]["outcome"]
        require("instance=SPECIAL tokenInput=StreamPosition$Shade$1 tokenOutput=StreamPosition$Shade" in kinds,
                "different enum instance or constant-specific class token")
        for extra in ("absent","missing","valued"):
            key = "30" if side == "old" or extra == "absent" else "null"
            require(data["filteredBlock"][side+"-"+extra] == f"block={1 if extra == 'absent' else 2} selected=1 sort={key}",
                    "different filtered-block evidence")
    return {"axisTransitions":len(data["axes"]),"eligibleAxisTransfers":sum(r["eligible"] for r in data["axes"]),
            "kryoFreshStreams":12,"filteredIndexReadbacks":len(data["filteredBlock"]),"sha256":upgrade_replay.sha(path)}


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
    pairs = {p.parent.name:audit_release_pair(HERE/"cases"/p.parent.name,p) for p in sorted((HERE/"results").glob("*/release-and-pr.json.gz"))}
    result = {"jobs":dict(Counter(j["status"] for j in jobs)), "outputDigests":sum(len(j["outputs"]) for j in jobs),
              "cases":records,"checkedContinuations":checked,"releasePairs":pairs}
    if (order := HERE/"results/J13/checked-order.json.gz").is_file():
        result["mavenOrder"] = audit_order(order)
    if (controls := HERE/"results/transfer-controls.json").is_file():
        result["transferControls"] = audit_transfers(controls)
    if args.write:
        change_evidence.write_json(HERE/"audit.json",result)
    elif (HERE/"audit.json").exists():
        require(result == read(HERE/"audit.json"), "campaign index differs")
    print(len(records),"first frozen plans,",result["jobs"],result["outputDigests"],"output digests,",
          sum(r["receiptReferences"] for r in records),"public receipt references verified")


if __name__ == "__main__":
    main()
