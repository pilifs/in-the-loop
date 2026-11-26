"""Verify the supplementary questions separately from the original frozen campaign."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

HERE = Path(__file__).resolve().parent


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def measured(archive, plan_name, bundle_name):
    with zipfile.ZipFile(HERE/archive) as z:
        def read(member):
            return json.loads(z.read(str(member)))
        plan = read(plan_name)
        bundle = PurePosixPath(bundle_name)
        generation = read(bundle/"generation.json")
        reg = read(bundle/"registration.json")
        rows = []
        for q, node in zip(reg["questions"], plan["claims"], strict=True):
            require(node["id"] == q["id"] and node["status"] == "established", "supplementary question failed")
            member = PurePosixPath(plan_name).parent / node["receipt"]["path"]
            raw = z.read(str(member))
            require(hashlib.sha256(raw).hexdigest() == node["receipt"]["sha256"], "different public receipt")
            receipt = json.loads(raw)
            require(receipt["generatedObserver"]["classes"] == generation["compiled"], "different caller classes")
            require(set(receipt["sides"]) == {"old", "new"}, "missing original deployment")
            sides = {}
            for side, deployed in receipt["sides"].items():
                samples = []
                for index, (item, trial) in enumerate(zip(q["inputs"], deployed["trials"], strict=True)):
                    a,b = trial["observations"]
                    x,y = trial["publicProjections"]
                    require(a == b and x == y and trial["input"] == index and trial["qualifiedMethodEntries"] == 2,
                            "incomplete repeat at the original entry")
                    fields = json.loads(a["return"])
                    digest = hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    require(x["observationSha256"] == digest and x["entryCalls"] > 0, "different public field projection")
                    if "conversions" in item:
                        require(x["numericArguments"] == item["conversions"], "numeric public inputs differ from the registration")
                    changed = {chain[0] for rep in trial.get("changedBodyChains", []) for chain in rep}
                    samples.append({"entryCalls": x["entryCalls"], "fields": fields, "changedMethodsUnderEntry": sorted(changed)})
                require(deployed["entryBinding"] == node["entryBindings"][side], "different original entry")
                sides[side] = samples
            rows.append({"question": q["id"], "history": q["history"], "inputs": q["inputs"], "entry": reg["entry"],
                         "status": node["status"], "generated":True, "compiled":True, "reachedBoth":True, "fullyObserved":True,
                         "assertedSides": q["sides"], "sides": sides,
                         "compilePolicy": generation["compilePolicy"], "archive": archive,
                         "registration": str(bundle/"registration.json"), "generation": str(bundle/"generation.json"),
                         "receipt": {"member": str(member), "sha256": node["receipt"]["sha256"]}})
        return rows


def score():
    collector = json.loads((HERE/"collector.json").read_bytes())
    published = {name: digest for job in collector.values() if job["status"] == "passed" for name, digest in job["outputs"].items()}
    for name in ("458-format-clean", "458-format-controls", "458-format-rescore", "numbered-inputs", "numbered-input-stops"):
        path = HERE/"receipts"/(name+".zip")
        require(published.get(path.relative_to(HERE.parents[1]).as_posix()) == hashlib.sha256(path.read_bytes()).hexdigest(),
                "supplementary archive differs from the collector: " + name)
    def member(archive, name):
        with zipfile.ZipFile(HERE/"receipts"/archive) as z:
            return json.loads(z.read(name))
    rows = measured("receipts/458-format-clean.zip", "cold.json", "bundle")
    historical = member("number-format-open.zip", "bundle/registration.json")["questions"][0]
    require((historical["id"], historical["inputs"]) == (rows[0]["question"], rows[0]["inputs"]), "different first format question")
    handoff = member("numbered-inputs.zip", "handoff.json")
    for case, folder in (("458","458-spring-positive-hex"), ("445","445-vavr-matched-null")):
        require(case in handoff["preflight"]["toProve"] and case in handoff["afterResume"]["decided"], "incomplete numbered handoff")
        records = "examples/" + folder + "/records/"
        rows += measured("receipts/numbered-inputs.zip", records+"public-replay.json", records+"public-observer")

    controls = member("458-format-controls.zip", "controls.json")
    refused = {}
    for key in ("text", "target-class", "locale", "pattern", "parsing-mode"):
        baseline = controls["null-format" if key == "target-class" else "formatted"]["raw"]
        require(controls[key]["raw"] == baseline and "refusal" in controls[key], "equal-output input substitution qualified")
        refused[key] = controls[key]["refusal"]
    rescores = json.loads((HERE/"baseline-rescores.json").read_bytes())
    updates = {}
    for case in rescores.values():
        scored = case["adjudications"]
        states = {k:s["status"] for k,s in scored.items()}
        require(states == {"registered":"open", "correctedParent":"established", "wrongFix":"refuted"}
                and len({s["observationsSha256"] for s in scored.values()}) == 1, "offline predicates changed measured evidence")
        updates[case["question"]] = {"adjudications":states, "rawSha256":scored["registered"]["observationsSha256"]}
    pair = [member("458-format-rescore.zip", n+".json")["claims"][0] for n in ("historical", "corrected")]
    require([n["status"] for n in pair] == ["open", "established"] and pair[0]["receipt"] == pair[1]["receipt"],
            "a single complete open question could not be re-scored")
    stops = member("numbered-input-stops.zip", "first-stops.json")
    limit = stops["formatter-after-return"]
    question, = limit["questions"]
    rows.append({"question":question["id"], "history":question["history"], "entry":limit["entry"],
                 "inputDefaults":limit["inputDefaults"], "registeredPredicates":question["expected"],
                 "assertedSides":["old","new"], "status":"open", "generated":False, "compiled":False,
                 "reachedBoth":False, "fullyObserved":False, "firstOpenDependency":limit["review"]["firstOpenDependency"],
                 "archive":"receipts/numbered-input-stops.zip", "record":"first-stops.json"})
    counts = {key:sum(r[key] for r in rows) for key in ("generated","compiled","reachedBoth","fullyObserved")}
    counts["questions"] = len(rows)
    counts["finite"] = {state:sum(r["status"] == state for r in rows) for state in ("established","open")}
    return {"rows":rows, "counts":counts, "equalOutputInputSubstitutionsRejected":refused, "baselineRescores":updates,
            "singleQuestionRescore":"receipts/458-format-rescore.zip", "setupStops":"receipts/numbered-input-stops.zip",
            "incompleteFixtureAttempt":{"question":stops["formatter-unspecified"]["questions"][0]["id"],
                "reason":stops["formatter-unspecified"]["review"]["firstOpenDependency"]},
            "smallestUnsupported":{"question":question["id"], "operation":limit["read"], "reason":rows[-1]["firstOpenDependency"]}}
