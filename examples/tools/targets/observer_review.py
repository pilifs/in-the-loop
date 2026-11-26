"""Turn an existing numbered scalar or nullable-selection registration into Stage 3 inputs.

Only the history and separately supplied fixture meanings enter caller construction.
Decoding the numbered registration's predicates is a separate evaluator operation.
"""
import hashlib
import json
import os
from pathlib import Path
import re

from targets import change_evidence, entry_discovery, observer_recipes, runtime_jar, runtime_jdk, upgrade_replay

write = change_evidence.write_json
LITERAL = r"`([^`\n]*)`"
NUMBER = r"(?:" + "|".join(sorted(observer_recipes.NUMBERS)) + r")\b"
JOIN = r"(?:\s+(?:and then|and|then)\s+|\s*,\s*(?:(?:and then|and|then)\s+)?)"
CONVERSIONS = re.compile(rf"(?P<texts>{LITERAL}(?:{JOIN}{LITERAL})*)\s+(?:as|with|to)\s+"
                         rf"(?P<types>{NUMBER}(?:{JOIN}{NUMBER})*)")
MISSING_FORMAT = "which NumberFormat should the numbered caller pass (explicit null or pattern, locale and parsing mode)?"


def numeric_history(history, defaults=None):
    """Consume every literal, type and operation in order, including text that should fail to parse."""
    rest = history.strip().removesuffix(".")
    intro = re.match(r"(?i)(?:at the landing,\s*)?(?:parse|try|convert)\s+(?:both\s+)?", rest)
    if not intro:
        raise observer_recipes.Unsupported("which text and numeric target type should the public parser receive?")
    rest = rest[intro.end():]
    defaults = defaults or {}
    marker = " using the registered NumberFormat"
    fixture = {"format": defaults["numberFormat"]} if "numberFormat" in defaults else {}
    conversions = []
    while True:
        group = CONVERSIONS.match(rest)
        if not group:
            raise observer_recipes.Unsupported("supply the literal text and requested numeric types for: " + rest[:160])
        conversions.extend({"text": text, "type": kind, **fixture} for text in re.findall(LITERAL, group["texts"])
                           for kind in re.findall(NUMBER, group["types"]))
        rest = rest[group.end():]
        if rest.startswith(marker):
            if "numberFormat" not in defaults:
                raise observer_recipes.Unsupported(MISSING_FORMAT)
            rest = rest[len(marker):]
            if rest:
                raise observer_recipes.Unsupported("unresolved operation after the public conversion: " + rest.lstrip(", ")[:160])
        if not rest:
            return {"conversions": conversions}
        join = re.match(JOIN, rest)
        if not join:
            raise observer_recipes.Unsupported("unresolved operation after the public conversion: " + rest.strip()[:160])
        rest = rest[join.end():]


def java_integer(value):
    try:
        numeric = int(value)
    except ValueError as error:
        raise observer_recipes.Unsupported("the selected input must be a Java Integer") from error
    if not -(2**31) <= numeric < 2**31:
        raise observer_recipes.Unsupported("the selected integer input lies outside the Java Integer range")
    return numeric


def nullable_values(sequence):
    if not sequence.strip():
        return []
    values = [v.strip() for v in sequence.split(",")]
    if any(v != "null" and not re.fullmatch(r"-?[0-9]+", v) for v in values):
        raise observer_recipes.Unsupported("specify the nullable integer sequence")
    return [None if v == "null" else java_integer(v) for v in values]


def integer_predicate(text):
    text = re.sub(r"^selecting\s+", "", text.strip(), flags=re.I)
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    if text.lower() in ("odd", "odd values"):
        return {"odd": True}
    if m := re.fullmatch(r"(?:values\s*)?>\s*(-?[0-9]+)", text):
        return {"greaterThan": java_integer(m[1])}
    if m := re.fullmatch(r"null or (-?[0-9]+)", text):
        return {"oneOf": [None, java_integer(m[1])]}
    if re.fullmatch(r"([A-Za-z_]\w*)\s*->\s*\1\s*==\s*null", text):
        return {"oneOf": [None]}
    raise observer_recipes.Unsupported("which predicate should select from the sequence at: " + text[:160])


def selection_history(history, defaults):
    if type(defaults.get("fallback")) != int:
        raise observer_recipes.Unsupported("what integer does the counting fallback supplier return?")
    fallback = java_integer(defaults["fallback"])
    history = history.strip().removesuffix(".")
    if m := re.fullmatch(r"`?(?:[\w.]+\.)?(?:<Integer>)?of\(([^()]*)\)`?,\s*with\s+(.+)", history):
        values = [nullable_values(m[1])]
        predicates = [integer_predicate(m[2])]
    elif m := re.fullmatch(r"(?i:use)\s+\[([^]\n]*)\](\s+twice)?[, ]+\s*(?:first\s+)?(.+)", history):
        values = [nullable_values(m[1])]
        predicates = [integer_predicate(part) for part in re.split(r",?\s+(?:and )?then\s+", m[3])]
        if m[2] and len(predicates) != 2:
            raise observer_recipes.Unsupported("which two ordered selections should inspect the sequence?")
    elif m := re.fullmatch(r"(?i:(?:on the merge )?select) (.+?)\.\s+(?i:compare) \[([^]\n]*)\] with \[([^]\n]*)\]"
                           r"(?:\.\s+(?i:append) (?:a further |another )?(?:rejected )?(-?[0-9]+) to each and search again)?", history):
        values = [nullable_values(m[2]), nullable_values(m[3])]
        predicates = [integer_predicate(m[1])]
        if m[4] is not None:
            values += [v + [java_integer(m[4])] for v in values]
    else:
        raise observer_recipes.Unsupported("specify the ordered sequence, its predicates, and each subsequent selection")
    return {"selections": [{"values": v, "predicate": p} for v in values for p in predicates],
            "fallback": fallback}


def prediction(family, expected):
    if expected.keys() != {"return"}:
        raise observer_recipes.Unsupported("need a typed evaluator mapping for this numbered predicate")
    raw = expected["return"]
    result = []
    if family == "number":
        for word in raw.split():
            if "=" in word:
                kind, value = word.split("=",1)
                if kind not in observer_recipes.NUMBERS:
                    raise ValueError("unknown registered numeric type")
                result.append(["return", ("java.math." if kind.startswith("Big") else "java.lang.")+kind, value])
            elif re.fullmatch("[A-Za-z]+Exception",word):
                result.append(["throws","java.lang."+word])
            else:
                raise ValueError("unknown registered numeric predicate")
    else:
        for sample in raw.split(","):
            m = re.fullmatch(r"(true|false)/(null|-?\d+)/(\d+)",sample)
            if not m: raise ValueError("unknown registered lazy-selection predicate")
            result.append([m[1]=="true",None if m[2]=="null" else int(m[2]),int(m[3])])
    return result


def prepare(folder, options, work):
    spec = json.loads((folder/"comparison.json").read_bytes())
    runtime = json.loads((folder/"runtime.json").read_bytes())
    if spec.get("schema") != "public-comparison/v1":
        raise observer_recipes.Unsupported("unknown numbered public comparison")
    profile = options.get("deployment","pins")
    deployment = runtime["deployments"][profile]
    if set(deployment)-{"classpath","providers","compileAgainst"} or deployment.get("compileAgainst","parent")!="parent":
        raise observer_recipes.Unsupported("this numbered deployment needs its additional compilation or fixture profile")
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK",Path.home()/".sdkman/candidates/java"/runtime["jdk"]))
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE",Path.home()/".cache/in-the-loop"/runtime["cache"]))
    paths = {"jdk":jdk}
    apis = {}
    for side, label in (("old","parent"),("new","fix")):
        rows=[{"file":str((cache / key).resolve(strict=True)),"sha256":runtime["sha256"][key]}
              for key in deployment["classpath"][label]]
        if any(upgrade_replay.sha(r["file"]) != r["sha256"] for r in rows) or upgrade_replay.sha(jdk/"release") != runtime["jdkReleaseSha256"]:
            raise ValueError("numbered artifact or JDK differs from its registered profile")
        apis[side] = observer_recipes.API([Path(r["file"]) for r in rows],int(runtime_jdk.identity(jdk)["feature"]))
        paths["before" if side=="old" else "after"] = work/(side+".json")
        write(work/(side+".json"),{"classpath":rows,"jdkReleaseSha256":runtime["jdkReleaseSha256"],
                                 "commit":spec["revisions"][label],"scope":"original numbered public-comparison deployment"})
    simple, _, method = spec["entry"].rpartition(".")
    owner = apis["old"].named(simple)
    api = apis["old"]
    declarations = [d for n,d in runtime_jar.methods(api.definition(owner)) if n==method]
    defaults = options.get("inputDefaults", {})
    numeric = observer_recipes.FORMATTED_NUMBER_ENTRY if "numberFormat" in defaults else observer_recipes.NUMBER_ENTRY
    candidates=[("number",d) for d in declarations if d==numeric]+[
        ("selection",d) for d in declarations if re.fullmatch(r"\(Ljava/util/function/Predicate;\)L[\w/$]+;",d)]
    if not candidates and "numberFormat" not in defaults and observer_recipes.FORMATTED_NUMBER_ENTRY in declarations:
        raise observer_recipes.Unsupported(MISSING_FORMAT)
    if len(candidates)!=1:
        raise observer_recipes.Unsupported("choose the public signature and its typed observation for " + spec["entry"])
    family, desc = candidates[0]
    if family == "selection" and "numberFormat" in defaults:
        raise observer_recipes.Unsupported("the supplied NumberFormat needs a numeric public entry")
    data=[side.definition(owner) for side in apis.values()]
    fps=[entry_discovery.fingerprints(entry_discovery.Definition(owner,hashlib.sha256(v).hexdigest(),0,v)) for v in data]
    changed=sorted(owner+"#"+n+d for n,d in fps[0].keys()|fps[1].keys() if fps[0].get((n,d))!=fps[1].get((n,d)))
    questions, expected = [], {}
    for q in spec["questions"]:
        item = numeric_history(q["history"], defaults) if family=="number" else selection_history(q["history"], defaults)
        sides={s:q["expected"][k] for s,k in [("old","parent"),("new","fix")] if k in q["expected"]}
        questions.append({"id":q["id"],"history":q["history"],"sides":list(sides),"inputs":[item],
                          "cohort":"control" if q["role"]=="Control" else "registered"})
        expected[q["id"]] = {s:[prediction(family,value)] for s,value in sides.items()}
    fields = ["call.outcome","return.type","return.value"] if family=="number" else ["result.defined","fallback.value","fallback.calls"]
    paths.update(registration=work/"registration.json",predictions=work/"predictions.json")
    write(paths["registration"],{"schema":"reviewed-public-observations/v1","change":spec["questions"][0]["id"].rsplit(".",1)[0],
          "entry":owner+"#"+method+desc,"changed":changed,"fields":fields,"questions":questions,
          "assumptions":["Fresh JVM and pinned original artifacts, one finite synchronous history at a time."]})
    write(paths["predictions"],expected)
    write(work/"review.json",{"comparisonSha256":upgrade_replay.sha(folder/"comparison.json"),
          "runtimeSha256":upgrade_replay.sha(folder/"runtime.json"),"deployment":profile,"semanticDefaults":options.get("inputDefaults",{}),
          "inputSources":["registered history","approved fixture meanings","public declarations"],
          "evaluatorSource":"side-scoped numbered predictions", "authoredCallerRead":False})
    return paths


def saved_setup(folder):
    """Read the numbered scaffold offline. Its planned entries confer no execution or proof verdict."""
    from targets import change_plan, observer_generation
    from targets.change_inventory import digest
    records = folder / "records"
    bundle = records / "public-observer"
    generation = json.loads((bundle/"generation.json").read_bytes())
    if generation.get("status") != "compiled":
        raise ValueError(generation.get("firstOpenDependency","no compiled public observer"))
    scaffold = json.loads((records/"entry-bindings.json").read_bytes())
    review = records/"reviewed-public-inputs/review.json"
    spec = json.loads((bundle/"registration.json").read_bytes())
    predictions = None
    if review.parent.exists() or "numberedReviewSha256" in scaffold:
        reviewed = json.loads(review.read_bytes())
        if reviewed.get("status") == "open":
            raise ValueError(reviewed["firstOpenDependency"])
        if "numberedReviewSha256" in scaffold and scaffold["numberedReviewSha256"] != upgrade_replay.sha(review):
            raise ValueError("the numbered review differs from the completed scaffold")
        if (reviewed["comparisonSha256"] != upgrade_replay.sha(folder/"comparison.json")
                or reviewed["runtimeSha256"] != upgrade_replay.sha(folder/"runtime.json")):
            raise ValueError("the numbered prediction or runtime changed after scaffold-only")
        if json.loads((review.parent/"registration.json").read_bytes()) != spec or any(
                observer_generation.portable_manifest(review.parent/(s+".json")) != json.loads((bundle/(s+".json")).read_bytes())
                for s in ("old", "new")):
            raise ValueError("the numbered inputs or deployments differ from the frozen caller")
        predictions = json.loads((review.parent/"predictions.json").read_bytes())
    _, workflows = change_plan.frozen_workflows(bundle/"workflows.json")
    check = change_plan.saved_bindings(scaffold)
    bound = {(e["claim"],e["side"]) for e in check["claims"] if e["deploymentQuestion"]=="adapted" and e["status"]=="bound"}
    questions = {q["id"]: q for q in spec["questions"]}
    if set(workflows) != set(questions) or (predictions is not None and set(predictions) != set(questions)):
        raise ValueError("the scaffold omits a registered question")
    nodes={n["id"]:n for n in scaffold["claims"]}
    if set(nodes)!=set(workflows):
        raise ValueError("the entry-binding plan identifies different questions")
    for name,(row,_,_,scope) in workflows.items():
        if predictions is not None:
            cases, changes = observer_generation.finite_domain(questions[name], predictions[name])
            if cases != scope["cases"] or row["intent"] != ({"allowedChanges": changes} if changes else "preserve"):
                raise ValueError("the numbered predictions differ from the frozen scope")
        if any((name,side) not in bound for side in ("old","new")):
            raise ValueError("public entry still requires a binding for " + name)
        if nodes[name]["claimKey"] != digest({"scope":scope,"intent":row["intent"],"assumptions":row["assumptions"]}):
            raise ValueError("reviewed expectation or scope differs from the bound plan")
    return bundle, list(workflows)


def resume_numbered(folder):
    from targets import change_plan
    bundle,_=saved_setup(folder)
    records=folder/"records"
    runtime=json.loads((folder/"runtime.json").read_bytes())
    jdk=Path(os.environ.get("PUBLIC_COMPARISON_JDK",Path.home()/".sdkman/candidates/java"/runtime["jdk"]))
    report=records/"public-replay.json"
    status=change_plan.main(["application","--before",str(bundle/"old.json"),"--after",str(bundle/"new.json"),
        "--jdk",str(jdk),"--workflows",str(bundle/"workflows.json"),"--previous",str(records/"entry-bindings.json"),
        "--supplied-only","--run","--output",str(report)])
    if status:
        raise ValueError("generated numbered replay could not qualify its original inputs")
    return json.loads(report.read_bytes())


def finite_answers(folder):
    """Derive each numbered verdict from its bound, repeated JVM receipts under the reviewed scope."""
    from targets import change_plan
    from targets.change_inventory import digest
    bundle,names = saved_setup(folder)
    answers = {name:None for name in names}
    path = folder/"records/public-replay.json"
    if not path.is_file():
        return answers
    plan = json.loads(path.read_bytes())
    if plan.get("executionState") != "complete":
        return answers
    change_plan.saved_bindings(plan,path.parent)
    _, scopes = change_plan.frozen_workflows(bundle/"workflows.json")
    for node in plan["claims"]:
        name = node["id"]
        if name not in scopes or node["status"]=="open":
            continue
        row,_,_,spec=scopes[name]
        expected_key=digest({"scope":spec,"intent":row["intent"],"assumptions":row["assumptions"]})
        if expected_key != node["claimKey"]:
            continue
        ref=node["receipt"]
        file=(path.parent/ref["path"]).resolve()
        if not file.is_relative_to(path.parent.resolve()) or upgrade_replay.sha(file)!=ref["sha256"]:
            raise ValueError("numbered evidence differs from the published JVM receipt")
        actual=json.loads(file.read_bytes())
        if actual.get("generatedObserver",{}).get("bundle")!=spec["generatedObserver"]["sha256"]:
            raise ValueError("numbered evidence belongs to another compiled observer")
        composed=change_evidence.compose(spec,actual,row["intent"])
        if composed["status"]!=node["status"]:
            raise ValueError("numbered finite verdict disagrees with its qualified observations")
        answers[name]=composed["status"]
    return answers
