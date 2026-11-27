"""Freeze public behavior candidates from a production-only PR packet, without running a subject."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import entry_discovery, observer_recipes, observer_scalar, runtime_jar, runtime_jdk


LIMIT = observer_recipes.CANDIDATE_BUDGET
SOURCE_BYTES = 512 * 1024
MAX_TYPES = 256
JAVA_NAME = r"[A-Za-z_$][\w$]*"
SCALAR_FIELDS = observer_scalar.FIELDS
SCALAR_TYPES = observer_scalar.TYPES
LITERAL = re.compile(r'"([^"\\\n]{0,80})"|\b(true|false|-?[0-9]{1,8})\b')
RETURN_LITERAL = r'(?:null|true|false|-?[0-9]{1,8}|"[^"\\\n]{0,80}")'
SAMPLE_TEXT = re.compile(r"[\w +,.:\-]{0,48}")


def ordinary_text(value):
    return not isinstance(value,str) or (SAMPLE_TEXT.fullmatch(value) is not None and ".." not in value)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_local(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("public input is outside the exported packet")
    return path


def tokens(value):
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return set(re.findall(r"[a-z0-9]{3,}", words.lower()))


def visible_sources(root, packet):
    by_owner = defaultdict(dict)
    for row in packet.get("productionSources", []):
        path = read_local(root, row["file"])
        if path.suffix != ".java" or not re.fullmatch(JAVA_NAME, path.stem):
            continue
        raw = path.read_bytes()
        if row.get("visibleSha256") and digest(raw) != row["visibleSha256"]:
            raise ValueError("changed visible production source")
        text = raw[:SOURCE_BYTES].decode("utf-8", "replace")
        package = re.search(r"\bpackage\s+([\w.]+)\s*;", text)
        owner = (package[1] + "." if package else "") + path.stem
        by_owner[owner][row["side"]] = text
    return by_owner


def definitions(root, rows, owners, feature):
    result = {}
    outer = {name.replace(".", "/") for name in owners}
    for index, row in enumerate(rows):
        path = read_local(root, row["file"])
        if path.is_dir():
            entries = [(name.relative_to(path).as_posix(), name) for owner in sorted(outer)
                       for name in sorted((path/owner).parent.glob((path/owner).name + "*.class"))]
            def read(name):
                return name.read_bytes()
            archive = None
        else:
            archive = zipfile.ZipFile(path)
            entries = runtime_jar.effective_entries(archive, feature).items()
            read = archive.read
        try:
            for name, actual in entries:
                if not name.endswith(".class") or name[:-6].split("$",1)[0] not in outer:
                    continue
                owner = name[:-6].replace("/", ".")
                if owner in result or len(result) >= MAX_TYPES:
                    continue
                data = read(actual)
                result[owner] = (entry_discovery.Definition(name, digest(data), 0, data), index, row["sha256"])
        finally:
            if archive is not None:
                archive.close()
    return result


def signature_candidates(sides, diff, hint, test_text, reviewed):
    changed = set()
    public = {}
    for owner in sorted(set(sides["old"]) | set(sides["new"])):
        methods = {}
        for side, bindings in sides.items():
            if owner not in bindings:
                continue
            definition, index, artifact = bindings[owner]
            fp = entry_discovery.fingerprints(definition)
            methods[side] = fp
            exported = runtime_jar.class_flags(definition.data) & 1
            for key,(flags,calls) in definition.methods().items():
                if exported and flags & 1 and not flags & (0x40 | 0x1000) and key[0] != "<clinit>":
                    item = public.setdefault((owner,*key), {})
                    item[side] = {"flags":flags, "calls":calls, "provider":index, "artifactSha256":artifact,
                                  "classSha256":definition.sha}
        for key in set(methods.get("old", {})) | set(methods.get("new", {})):
            if methods.get("old", {}).get(key) != methods.get("new", {}).get(key):
                changed.add((owner.replace(".", "/"), *key))
    eligible = []
    for (owner, name, desc), sides_for_entry in public.items():
        full = owner + "#" + name + desc
        in_diff = (owner.replace(".", "/"), name, desc) in changed
        direct = any(ref in changed for side in sides_for_entry.values() for ref in side["calls"])
        simple = owner.rsplit(".",1)[-1].split("$")[-1]
        short = simple if name == "<init>" else name
        nominated = bool(re.search(r"(?<![\w$])" + re.escape(short) + r"(?![\w$])", hint, re.I))
        review_entry = reviewed.get("entry", "")
        reviewed_match = bool(review_entry and any(review_entry == k for k in
            (full, owner+"."+name, owner+"#"+name, simple+"."+name, simple+"#"+name, simple+"."+short)))
        if not (in_diff or direct or reviewed_match or nominated):
            continue
        priority = (not reviewed_match, not nominated, not in_diff, not direct, -len(sides_for_entry), full)
        eligible.append((priority,owner,name,desc,short,full,in_diff,direct,nominated,reviewed_match,sides_for_entry))
    inspected = sorted(eligible, key=lambda r:r[0])[:LIMIT]
    ranked = []
    for _,owner,name,desc,short,full,in_diff,direct,nominated,reviewed_match,sides_for_entry in inspected:
        test_reference = bool(test_text and re.search(r"\b" + re.escape(short) + r"\s*\(", test_text))
        arguments, returned = observer_scalar.parts(desc)
        scalar = all(arg in SCALAR_TYPES for arg in arguments) and returned in SCALAR_TYPES and name != "<init>"
        weight = (100*reviewed_match + 16*nominated + 10*in_diff + 9*direct + 12*test_reference
                  + 4*(len(sides_for_entry) == 2) + 3*scalar + min(6,len(tokens(short) & tokens(hint))*2)
                  + 3*(short + "(" in diff) + 2*(name != "<init>"))
        basis = [label for label, visible in (("reviewed entry",reviewed_match), ("named in PR prose",nominated),
                 ("changed declaration",in_diff), ("calls a changed member",direct), ("upstream test reference",test_reference)) if visible]
        ranked.append((weight,full,scalar,basis,{s:{k:v for k,v in value.items() if k != "calls"}
                                                for s,value in sides_for_entry.items()}))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return ranked, len(eligible), [r[5] for r in inspected]


def literal(text):
    if text == "null":
        return None
    if text in ("true","false"):
        return text == "true"
    if re.fullmatch(r"-?[0-9]{1,8}", text):
        return int(text)
    if re.fullmatch(r'"[^"\\\n]{0,80}"', text):
        return text[1:-1]
    raise ValueError("not a scalar source literal")


def method_text(source, method, arity):
    """Use a unique same-arity declaration only. Keep ambiguous overloads as a prediction gap."""
    found = []
    header = re.compile(r"(?m)^[ \t]*(?:(?:public|private|protected|static|final|synchronized|default|abstract|native)\s+)+"
                        r"[^;{}=]*?\b" + re.escape(method) + r"\s*\(([^(){}]*)\)\s*(?:throws\s+[^{};]+)?\{")
    for match in header.finditer(source):
        args = [p.strip() for p in re.sub(r"<[^<>]*>","",match[1]).split(",") if p.strip()]
        if len(args) != arity:
            continue
        depth = 1
        for token in re.finditer(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[{}]',source[match.end():match.end()+32768]):
            if token[0] not in "{}":
                continue
            depth += 1 if token[0] == "{" else -1
            if not depth:
                found.append(([a.split()[-1] for a in args], source[match.end():match.end()+token.start()].strip()))
                break
    return found[0] if len(found)==1 else ([], "")


def predicted_return(body, names, args, returned):
    expression = re.fullmatch(r"return\s+(" + RETURN_LITERAL + r"|[\w$]+)\s*;", body)
    if expression is None:
        return None
    name = expression[1]
    try:
        result = args[names.index(name)] if name in names else literal(name)
    except ValueError:
        return None
    if not observer_scalar.accepts(returned, result):
        return None
    spelling = str(result).lower() if type(result) is bool else str(result)
    return ["return", None, None] if result is None else ["return", "java.lang." + SCALAR_TYPES[returned], spelling]


def test_examples(text, method, types):
    """Read literal examples only. Source assertions are candidate evidence before original executions."""
    calls = []
    for match in re.finditer(r"\b" + re.escape(method) + r"\s*\(([^()\n;]{0,200})\)",text):
        words = re.findall(RETURN_LITERAL, match[1])
        if re.sub(r"\s+","","".join(re.split(RETURN_LITERAL, match[1]))) != ","*max(0,len(words)-1):
            continue
        args = [literal(w) for w in words]
        if len(args) == len(types) and all(ordinary_text(v) and observer_scalar.accepts(t,v) for t,v in zip(types,args)):
            item = {"arguments":args}
            if item not in calls:
                calls.append(item)
        if len(calls)==8:
            break
    return calls


def scalar_cases(descriptor, evidence):
    params, _ = observer_scalar.parts(descriptor)
    spellings = [m.group() for m in LITERAL.finditer(evidence)]
    strings = [literal(x) for x in spellings if x.startswith('"') and ordinary_text(literal(x))]
    numbers = [literal(x) for x in spellings if re.fullmatch(r"-?[0-9]{1,8}",x)]
    values = []
    for typ in params:
        if typ == "Ljava/lang/String;":
            values.append(list(dict.fromkeys([*strings[:2],"","a",None])))
        elif typ == "Z":
            values.append([False,True])
        elif typ == "C":
            values.append(["a","0"])
        else:
            limits = {"B":(-128,127), "S":(-32768,32767)}
            low, high = limits.get(typ, (-(2**31),2**31-1))
            values.append(list(dict.fromkeys([n for n in numbers[:3] if low <= n <= high] + [0,1,-1])))
    count = max((len(v) for v in values),default=1)
    return [{"arguments": [v[i%len(v)] for v in values]} for i in range(count)]


def derive(root, packet):
    arm = packet["arm"]
    if arm not in {"cold","test-assisted","reviewed"}:
        raise ValueError("unknown public evidence phase")
    if (arm != "test-assisted" and packet.get("upstreamTests")) or (arm != "reviewed" and packet.get("reviewed")):
        raise ValueError("additional evidence in a sealed public view")
    sources = visible_sources(root, packet)
    diff = read_local(root, packet["productionDiff"]).read_bytes()[:SOURCE_BYTES].decode("utf-8","replace")
    title = packet.get("title","")
    prose = title + "\n" + packet.get("description","")
    reviewed = packet.get("reviewed") or {}
    tests = []
    for row in (packet.get("upstreamTests") or [])[:32]:
        tests.append(read_local(root,row["file"]).read_bytes()[:65536].decode("utf-8","replace"))
    test_text = "\n".join(tests)
    version = runtime_jdk.release(Path(packet["jdk"]))["JAVA_VERSION"]
    feature = int(runtime_jdk.feature(version))
    sides = {s:definitions(root, packet[s]["classpath"], sources, feature) for s in ("old","new")}
    ranked, count, inspected = signature_candidates(sides, diff, prose, test_text, reviewed)
    candidates = []
    for rank,(weight, entry, scalar, basis, bindings) in enumerate(ranked[:LIMIT], 1):
        if len(candidates) == 3:
            break
        owner, method, desc = runtime_jar.parse_target(entry)
        simple = owner.rsplit(".",1)[-1]
        called = simple + "." + method if method != "<init>" else "new " + simple
        types, returned = observer_scalar.parts(desc)
        roots = sources.get(owner.split("$",1)[0], {})
        bodies = {s:method_text(roots.get(s,""), method, len(types)) for s in ("old","new")}
        tests_for_call = test_examples(test_text, method, types) if scalar else []
        inputs = list(tests_for_call)
        if scalar:
            for item in scalar_cases(desc, prose + "\n" + bodies["new"][1]):
                if item not in inputs:
                    inputs.append(item)
        fields = list(SCALAR_FIELDS) if scalar else ["public return or escaping exception"]
        history = (f"Call {called} on each listed argument tuple and retain its return or escaping exception."
                   if scalar else f"Reach {called} from a public caller and observe its result under the change described by {title}.")
        predicate = {"relation":"different on at least one registered input"} if scalar else {"undecided":"public input and observation need registration"}
        if desc == observer_recipes.NUMBER_ENTRY:
            body = "\n".join([prose,bodies["old"][1],bodies["new"][1]])
            quoted = re.findall(r'["`]([+\-]?(?:0[xX]|#)?[0-9a-fA-F]+)["`]',body)
            prefixes = [x for x in ("0x","0X","#") if '"'+x+'"' in body]
            numbers = list(dict.fromkeys([*quoted,*(prefix+"1" for prefix in prefixes),"0","1","-1","+1"]))
            kinds = sorted(k for k in observer_recipes.NUMBERS if re.search(r"\b"+k+r"\.class\b",body)) or ["Integer"]
            inputs = [{"conversions":[{"text":word,"type":kind} for kind in kinds]} for word in numbers[:8]]
            fields = list(observer_recipes.NUMBER_FIELDS)
            history = f"Parse each registered spelling through {called} for the listed numeric classes. Observe its exact returned type and value or escaping exception."
            predicate = {"relation":"different on at least one registered input"}
        elif method == "peek" and desc == "()Ljava/lang/Object;":
            from targets import observer_public_data
            fields = list(observer_public_data.STACK_RETAINED)
            inputs = [{"capacity":4,"values":[],"drain":False},{"capacity":4,"values":[1],"drain":True},
                      {"capacity":4,"values":[1,2],"drain":False}]
            history = f"Call {called} on an initially empty, drained and populated stack. Read the following pop on each same receiver."
            predicate = {"relation":"different on at least one registered input"}
        if scalar:
            predicted = {s:[predicted_return(body,names,item["arguments"],returned) for item in inputs]
                         for s,(names,body) in bodies.items()}
            if all(x is not None for rows in predicted.values() for x in rows):
                predicate = {"expected":{s:[[x] for x in rows] for s,rows in predicted.items()},
                             "basis":"literal or identity return from unique public declarations"}
                history = f"Call {called} for each listed input and check its typed result against the two public declarations."
        if "reviewed entry" in basis:
            history = reviewed.get("history",history)
            fields = reviewed.get("fields",fields)
            inputs = reviewed.get("inputs",inputs)
            predicate = reviewed.get("prediction", reviewed.get("predictions", {"undecided":"side-specific expectation was not supplied"}))
        candidates.append({"rank":rank, "entry":entry, "history":history, "fields":fields, "inputs":inputs,
                           "prediction":predicate, "requiredSides":reviewed.get("requiredSides",["old","new"]),
                           "source":basis, "score":weight,"bindings":bindings, "publicChange":title,
                           "sourceMethodSha256":{s:digest(b.encode()) for s,(_,b) in bodies.items() if b},
                           "literalTestInputs":len(tests_for_call),
                           "recipe":"public scalar method" if scalar and fields == SCALAR_FIELDS else "reviewed public history"})
    return {"schema":"blind-public-prediction/v1", "url":packet["url"], "arm":arm,
            "assistance":{"cold":"public production changes", "test-assisted":"upstream test sources", "reviewed":"semantic registration"}[arm],
            "primary":0 if candidates else None, "candidates":candidates, "candidateBudget":LIMIT,
            "candidatesInspected":len(inspected), "inspectedEntries":inspected, "candidateCount":count,
            "sourceClasses":{s:len(v) for s,v in sides.items()}, "testsInspected":len(tests), "subjectLaunches":0,
            "visibleDescription":packet.get("description",""), "productionDiffSha256":digest(read_local(root,packet["productionDiff"]).read_bytes()),
            "firstOpenDependency":None if candidates else "which original public production entry exposes this change?"}


def publish(path, doc):
    encoded = (json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent) as stream:
        stream.write(encoded)
        stream.flush()
        try:
            os.link(stream.name, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError("a different prediction is already sealed here")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet",type=Path)
    parser.add_argument("output",type=Path)
    args = parser.parse_args(argv)
    raw = (args.packet/"packet.json").read_bytes()
    prediction = derive(args.packet, json.loads(raw))
    prediction["packetSha256"] = digest(raw)
    publish(args.output/"prediction.json", prediction)


if __name__ == "__main__":
    main()
