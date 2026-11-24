"""Qualify each original reader's key conversion, startup accessor and value diagnostic."""
import argparse
import gzip
import json
from pathlib import Path
import tempfile
import zipfile

from key_proof import certificate, digest, prove, require
from register import BASE, CALLERS, CASE, DIGITS, ENTRIES, PARSE, READER, TREE, sha
from freeze import verify
from live import compile_tracer, member_site, observe
from plan_run import OUTPUT, ROOT
from targets import change_inventory, runtime_jar

TARGET = ROOT / OUTPUT / "gson"
ACCESS = BASE + "internal.JsonReaderInternalAccess"


def deployment(side):
    doc = json.loads((CASE / side / "prepared.json").read_bytes())
    jars = [Path(r["file"]) for r in doc["classpath"]]
    require([sha(j) for j in jars] == [r["sha256"] for r in doc["classpath"]], "different deployed Gson")
    return doc, jars


def install_site(jar):
    data = runtime_jar.read_class(jar, READER.replace(".", "/"))
    cp, methods, _ = runtime_jar._declarations(data, with_code=True)
    code = methods["<clinit>", "()V"][1]
    ops = list(change_inventory.instructions(code))
    (put, opcode), (ret, end) = ops[-2:]
    ref = runtime_jar._member_ref(cp, cp[int.from_bytes(code[put+1:ret], "big")][1])
    require((opcode, end) == (0xb3, 0xb1) and ref == (ACCESS.replace(".", "/"), "INSTANCE", "Lcom/google/gson/internal/JsonReaderInternalAccess;"), "different accessor installation")
    return ret, digest(code), digest(data[10:runtime_jar._pool(data)[1]])


def config_file(path, proof, jar, route, mode, control=None):
    methods = {m: row for r in proof["rows"] for m, row in r["methods"].items()}
    props = {"entry": ENTRIES[route], "caller": CALLERS[route], "methods": ",".join(sorted(methods)),
             "installedAt": install_site(jar)[0], "mode": mode}
    for name, binding in methods.items():
        props["code." + name] = binding["code"]
        props["pool." + name] = binding["pool"]
    props.update({"value." + row["text"]: row["result"] for row in proof["rows"]})
    if control == "stale":
        props["code." + PARSE] = "00" * 32
    if control == "route":
        props["caller"] = CALLERS["tree" if route == "stream" else "stream"]
    path.write_text("".join(f"{k}={v}\n" for k, v in props.items()))


def check(trial, proof, receipt, node, child, side, mode):
    require(proof and trial["proofKey"] == proof["key"], "missing or stale decimal proof")
    args = child["arguments"]
    route, history, _ = args
    doc, jars = deployment(side)
    binding = receipt["sides"][side]
    require(trial["commit"] == doc["commit"] == binding["commit"] and binding["classpath"] == [r["sha256"] for r in doc["classpath"]], "different ordered deployment")
    ordinary = binding["trials"][child["input"]]
    require(trial["observation"] == child[side] and ordinary["observations"] == [child[side]] * 2 and ordinary["qualifiedMethodEntries"] == 2
            and trial["entrySite"] in ordinary["entryInvocations"] and trial["entrySite"]["dispatchedTo"] == ENTRIES[route]
            and trial["claimKey"] == node["claimKey"], "different public continuation")
    events = trial["events"]
    ret, code, pool = install_site(jars[0])
    require(events and events[0] == ["installed", READER + "#<clinit>()V", str(ret), code, pool, READER + "$1"], "missing installed original accessor")
    docs = [("1", "2")] if history == "plain" else [("1", "2"), ("01", "002"), ("002", "01")]
    cursor = 1
    for i, keys in enumerate(docs, 1):
        for j, name in enumerate(keys):
            rows = events[cursor:cursor+3]
            require(len(rows) == 3, "missing original map key")
            promote, parse, value = rows
            require(promote[:3] == ["promote", str(i), READER if route == "stream" else TREE], "wrong promoted reader")
            call = member_site(jars[0], promote[3:])
            require((call["owner"], call["name"], call["descriptor"]) == (ACCESS, "promoteNameToValue", "(Lcom/google/gson/stream/JsonReader;)V"), "unbound map promotion")
            require(parse[:5] == ["parse", name, str(DIGITS[name]), str(mode == "apply").lower(), CALLERS[route]], "missing checked decimal conversion")
            call = member_site(jars[0], parse[4:])
            require(call["owner"] + "#" + call["name"] + call["descriptor"] == PARSE and call["opcode"] == "invokestatic", "different parse call")
            require(value[:3] == ["value", name, str(DIGITS[name])], "original map value lost its key")
            call = member_site(jars[0], value[3:])
            require(call["owner"] == BASE + "TypeAdapter" and call["name"] == "read", "different map value read")
            cursor += 3
            if i == 2 and j == 1:
                require(cursor < len(events), "missing original failure")
                failure = events[cursor]
                require(failure[:3] == ["failure", name, "$." + (name if side == "new" else "")], "wrong original failing path")
                owner, member, desc = runtime_jar.parse_target(failure[3])
                require(owner == (READER if route == "stream" else TREE) and member == "nextString", "wrong throwing reader")
                data = runtime_jar.read_class(jars[0], owner.replace(".", "/"))
                b = runtime_jar._declarations(data, with_code=True)[1][member, desc][1]
                require(digest(b) == failure[5] and digest(data[10:runtime_jar._pool(data)[1]]) == failure[6]
                        and b[int(failure[4])] == 0xbf and failure[7].startswith("UpgradeProbe$ValueAdapter#read("), "unbound original throw or catch")
                cursor += 1
    require(cursor == len(events), "unexpected additional reader event")


def replay(work, classes, proof, side, args, mode, control=None):
    doc, jars = deployment(side)
    route = args[0]
    config = work / "config"
    config_file(config, proof, jars[0], route, mode, control)
    outcome, marks, site, origins = observe(classes, jars, ENTRIES[route], args, work / "vm", config,
                                            exceptions="java.lang.IllegalStateException")
    for name in (BASE + "Gson", READER, READER + "$1", ACCESS, BASE + "FormattingStyle", CALLERS[route].split("#")[0]):
        require(origins.get(name) == {jars[0]}, "different original provider for " + name)
    pc, member = site.split("\t")
    return {"commit": doc["commit"], "proofKey": proof["key"], "entrySite": {"observerCodeIndex": int(pc), "dispatchedTo": member},
            "observation": outcome, "events": marks}


def run():
    verify()
    proof = certificate()
    try:
        prove("002", 0)
    except ValueError as why:
        require(str(why) == "original parse disagrees with declared key", "unexpected false sibling disposition")
    else:
        raise ValueError("wrong decimal value admitted")
    report = {"proof": proof, "trials": [], "controls": {"wrongKey": "original parse disagrees with declared key"}}
    with tempfile.TemporaryDirectory(prefix="gson-original-keys-") as directory, zipfile.ZipFile(TARGET / "first/plans.zip") as archived:
        work = Path(directory)
        classes, report["tracer"] = compile_tracer(CASE, work, deployment("old")[1])
        nodes = json.loads(archived.read("cold.json"))["claims"]
        for node in nodes:
            if node["cohort"] != "registered": continue
            ref = node["receipt"]
            raw = archived.read(ref["path"])
            require(digest(raw) == ref["sha256"] and node["status"] == "established", "unbound original public plan")
            receipt = json.loads(raw)
            require(all(receipt["probeClasses"].get(p.stem) == sha(p) for p in classes.glob("UpgradeProbe*.class")),
                    "different public probe or value adapter")
            for child in node["children"]:
                args = child["arguments"]
                for side in ("old", "new"):
                    for mode in ("reference", "apply", "apply"):
                        trial_dir = work / str(len(report["trials"]))
                        trial_dir.mkdir()
                        trial = replay(trial_dir, classes, proof, side, args, mode)
                        trial.update(claimKey=node["claimKey"], claim=node["id"], receipt=ref, input=child["input"], mode=mode, side=side)
                        check(trial, proof, receipt, node, child, side, mode)
                        report["trials"].append(trial)
                    if args[1:] != ["mixed", "paths"]: continue
                    for control, reason in (("route", "wrong reader-specific parse consumer"), ("stale", "stale or uninitialized decimal method " + PARSE)):
                        place = work / (node["id"] + "-" + side + "-" + control)
                        place.mkdir()
                        try: replay(place, classes, proof, side, args, "apply", control)
                        except ValueError as e: require(reason in str(e), "unexpected live refusal: " + str(e))
                        else: raise ValueError("accepted " + control)
                        report["controls"][node["id"] + "-" + side + "-" + control] = reason
    (TARGET / "checked-keys.json.gz").write_bytes(gzip.compress(json.dumps(report, separators=(",", ":")).encode(), mtime=0))
    audit()


def audit():
    verify()
    registration = json.loads((CASE / "registration.json").read_bytes())
    require(all(sha(CASE / p) == value for p, value in registration["inputs"].items()), "different public registration")
    report = json.loads(gzip.decompress((TARGET / "checked-keys.json.gz").read_bytes()))
    require(report["proof"] == certificate(), "bytecode certificate differs")
    require(report["tracer"]["frozenTrace"] == sha(ROOT / "examples/tools/targets/java/UpgradeTrace.java")
            and report["tracer"]["caseFrames"] == sha(CASE / "CaseFrames.java")
            and report["tracer"]["frameValues"] == sha(CASE.parent / "FrameValues.java"), "different execution tools")
    required = {label + "-paths-" + side + "-" + control for label in ENTRIES for side in ("old", "new") for control in ("route", "stale")}
    require(set(report["controls"]) == required | {"wrongKey"}, "missing live or false-value control")
    with zipfile.ZipFile(TARGET / "first/plans.zip") as archive:
        nodes = {n["id"]: n for n in json.loads(archive.read("cold.json"))["claims"] if n["cohort"] == "registered"}
        counts = {}
        for trial in report["trials"]:
            node = nodes[trial["claim"]]
            ref = node["receipt"]
            blob = archive.read(ref["path"])
            require(trial["receipt"] == ref and digest(blob) == ref["sha256"], "wrong public receipt")
            receipt = json.loads(blob)
            child = node["children"][trial["input"]]
            check(trial, report["proof"], receipt, node, child, trial["side"], trial["mode"])
            k = (trial["claim"], trial["input"], trial["side"], trial["mode"])
            counts[k] = counts.get(k, 0) + 1
        expected = {(name, c["input"], side, mode): n for name, node in nodes.items() for c in node["children"]
                    for side in ("old","new") for mode, n in (("reference", 1), ("apply", 2))}
        require(counts == expected, "incomplete original/substituted trials")
        # A surviving physical value cannot make up for a missing installation, original call or failure observation.
        t = next(t for t in report["trials"] if t["claim"] == "tree-paths" and t["input"] == 1 and t["mode"] == "apply")
        node = nodes[t["claim"]]
        rec = json.loads(archive.read(node["receipt"]["path"]))
        for role in ("installed", "parse", "failure"):
            changed = t | {"events": [event for event in t["events"] if event[0] != role]}
            try: check(changed, report["proof"], rec, node, node["children"][1], t["side"], "apply")
            except ValueError: pass
            else: raise ValueError("withheld " + role + " accepted")
    print(len(report["trials"]), "original and substituted continuations requalified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    if parser.parse_args().audit: audit()
    else: run()
