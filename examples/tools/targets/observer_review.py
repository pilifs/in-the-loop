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
NUMBER = re.compile(r"\b(" + "|".join(sorted(observer_recipes.NUMBERS)) + r")\b")


def numeric_history(history):
    literals = list(re.finditer(r"`([+#0-9a-fA-FxX.-]+)`", history))
    if not literals:
        raise observer_recipes.Unsupported("which text and numeric target type should the public parser receive?")
    groups = [NUMBER.findall(history[m.end():n.start() if n else len(history)])
              for m,n in zip(literals, [*literals[1:],None])]
    if all(not group for group in groups[:-1]) and groups[-1]:
        groups = [groups[-1]] * len(literals)
    if any(not group for group in groups):
        raise observer_recipes.Unsupported("which requested numeric types belong to each input text?")
    return {"conversions":[{"text":m[1],"type":kind} for m,group in zip(literals,groups) for kind in group]}


def selection_history(history, defaults):
    if type(defaults.get("fallback")) != int:
        raise observer_recipes.Unsupported("what integer does the counting fallback supplier return?")
    seqs = re.findall(r"\[([^]\n]+)\]", history) or re.findall(r"\bof\(([^)]+)\)", history)
    values = []
    for seq in seqs:
        items = [s.strip() for s in seq.split(",")]
        if not all(s == "null" or re.fullmatch(r"-?\d+",s) for s in items):
            raise observer_recipes.Unsupported("specify the nullable integer sequence")
        values.append([None if s=="null" else int(s) for s in items])
    if not values:
        raise observer_recipes.Unsupported("which values and order should the selection inspect?")
    predicates = []
    if m := re.search(r">\s*(-?\d+)",history):
        predicates.append({"greaterThan":int(m[1])})
    if "odd" in history.lower():
        predicates.append({"odd":True})
    if m := re.search(r"null or (-?\d+)",history):
        predicates.append({"oneOf":[None,int(m[1])]})
    elif re.search(r"==\s*null",history):
        predicates.append({"oneOf":[None]})
    if not predicates or (len(values)>1 and len(predicates)>1):
        raise observer_recipes.Unsupported("which predicate should select from each sequence?")
    if m := re.search(r"append (?:a further |another )?(?:rejected )?(-?\d+) to each",history,re.I):
        values += [v+[int(m[1])] for v in values]
    return {"selections":[{"values":v,"predicate":p} for v in values for p in predicates],"fallback":defaults["fallback"]}


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
    numeric="(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Number;"
    candidates=[("number",d) for d in declarations if d==numeric]+[
        ("selection",d) for d in declarations if re.fullmatch(r"\(Ljava/util/function/Predicate;\)L[\w/$]+;",d)]
    if len(candidates)!=1:
        raise observer_recipes.Unsupported("choose the public signature and its typed observation for " + spec["entry"])
    family, desc = candidates[0]
    data=[side.definition(owner) for side in apis.values()]
    fps=[entry_discovery.fingerprints(entry_discovery.Definition(owner,hashlib.sha256(v).hexdigest(),0,v)) for v in data]
    changed=sorted(owner+"#"+n+d for n,d in fps[0].keys()|fps[1].keys() if fps[0].get((n,d))!=fps[1].get((n,d)))
    questions, expected = [], {}
    for q in spec["questions"]:
        item = numeric_history(q["history"]) if family=="number" else selection_history(q["history"], options.get("inputDefaults",{}))
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
