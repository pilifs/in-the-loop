"""Qualify exact, pure integral helper substitutions used by finite application histories."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from targets import change_evidence, change_inventory, runtime_jar, runtime_jdk
from targets.change_inventory import digest, instructions

TYPES = {"I": ("int", -(2**31), 2**31-1), "J": ("long", -(2**63), 2**63-1),
         "C": ("char", 0, 65535), "Z": ("boolean", 0, 1)}
IDENT = r"[a-zA-Z_$][a-zA-Z_$0-9]*"


def literal(value, kind):
    name, low, high = TYPES[kind]
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"helper table value outside {name}")
    if kind == "Z":
        return "true" if value else "false"
    if kind == "C":
        return f"(char){value}"
    return str(value) + ("L" if kind == "J" else "")


def original_class(owner, files, jdk):
    name = runtime_jar.internal(owner)
    feature = int(runtime_jdk.identity(jdk)["feature"])
    if owner.startswith("java."):
        module = jdk/"jmods/java.base.jmod"
        with zipfile.ZipFile(module) as jar:
            return jar.read("classes/" + name + ".class"), "java.base"
    for file in files:
        data = runtime_jar.effective_class(file, name, feature)
        if data is not None:
            return data, str(file)
    raise ValueError("helper missing from ordered deployment: " + owner)


def declaration(spec, data):
    owner, method, desc = runtime_jar.parse_target(spec["entry"])
    if not re.fullmatch(IDENT + r"(?:\." + IDENT + r")*", owner) or not re.fullmatch(IDENT, method):
        raise ValueError("invalid Java helper name")
    if not re.fullmatch(r"\([IJZC]*\)[IJZC]", desc or ""):
        raise ValueError("expected a primitive integral helper descriptor")
    _, methods, _ = runtime_jar._declarations(data, with_code=True)
    flags, code, _ = methods.get((method, desc), (0, None, None))
    if flags & 9 != 9 or flags & (0x20 | 0x100) or not code or not (runtime_jar.class_flags(data) & 1):
        raise ValueError("expected original public static bytecode without a synchronized frame")
    args = list(desc[1:desc.index(")")])
    names, _ = runtime_jar.parameter_names(data, method, desc)
    if not args or not all(re.fullmatch(IDENT, v) for v in names):
        raise ValueError("unsupported helper parameter names")
    rows = spec["rows"]
    if not rows or len({tuple(r["args"]) for r in rows}) != len(rows):
        raise ValueError("empty or ambiguous helper domain")
    target = owner + "#" + method + "(" + ",".join(TYPES[k][0] for k in args) + ")"
    guards, conclusions, branches = [], [], []
    for index, row in enumerate(rows):
        vals = [literal(v, k) for v, k in zip(row["args"], args, strict=True)]
        result = literal(row["result"], desc[-1])
        guard = " && ".join(f"{p} == {v}" for p, v in zip(names, vals))
        guards.append("(" + guard + ")")
        conclusions.append("(" + guard + " && result == " + result + ")")
        branches.append(f"case {index}: return {owner}.{method}({', '.join(vals)}) == {result};")
    contract = target + "\n  assume: " + " || ".join(guards) + "\n  assert: " + " || ".join(conclusions) + "\n"
    wrapper = ("public final class CheckedHelperUse { public static boolean check(int choice) { switch(choice) {\n"
               + "\n".join(branches) + "\ndefault: return false; } } }\n")
    cp = data[10:runtime_jar._pool(data)[1]]
    return contract, wrapper, {k: hashlib.sha256(v).hexdigest() for k, v in
                               [("classSha256", data), ("codeSha256", code), ("poolSha256", cp)]}


def local_integral_body(code, pool=None):
    """Only primitive constants, locals, arithmetic, conversion, comparison and control flow.
    No heap, calls, monitors, allocation, dynamic constants, or external reads can participate.
    Normal termination on every enumerated tuple is checked separately by a real JVM.
    """
    allowed = {0x00, *range(0x02, 0x0b), 0x10, 0x11, 0x15, 0x16, *range(0x1a, 0x22),
               0x36, 0x37, *range(0x3b, 0x43), *range(0x57, 0x60), *range(0x78, 0x86),
               0x88, 0x91, 0x92, 0x93, 0x94, *range(0x99, 0xa8), 0xaa, 0xab, 0xac, 0xad, 0xc8}
    for op in range(0x60, 0x78, 4):
        allowed.update((op, op+1))
    for offset, op in instructions(code):
        if op in (0x12, 0x13, 0x14):
            width = 1 if op == 0x12 else 2
            index = int.from_bytes(code[offset+1:offset+1+width], "big")
            # A dynamic constant can initialize classes even if its declared type is integral.
            if pool is None or pool.get(index, (None,))[0] != (5 if op == 0x14 else 3):
                return False
        elif op not in allowed:
            return False
    return True


def prove(spec, files, jdk, image, checker, directory, cache):
    from targets.upgrade_replay import sha
    owner, _, _ = runtime_jar.parse_target(spec["entry"])
    data, origin = original_class(owner, files, jdk)
    if spec.get("boundClassSha256") and hashlib.sha256(data).hexdigest() != spec["boundClassSha256"]:
        raise ValueError("actual helper class differs from the generated binding")
    contract, source, hashes = declaration(spec, data)
    rules = {path.name: sha(path) for path in
             (Path(__file__), Path(change_inventory.__file__), Path(runtime_jar.__file__), Path(runtime_jdk.__file__))}
    key = digest({"spec": spec, "helper": hashes, "jdk": image, "checker": sha(checker),
                  "qualification": rules, "ordered": [(str(f), sha(f)) for f in files],
                  "contract": contract, "consumer": source})
    stored = cache / (key+".json") if cache else None
    if stored and stored.is_file():
        try:
            envelope = json.loads(stored.read_bytes())
            record = envelope["evidence"]
            if (envelope["sha256"] == digest(record) and record["key"] == key and record["rows"] == spec["rows"]
                    and record["entry"] == spec["entry"] and record["provider"] == origin
                    and record["contract"] == contract and record["consumer"] == source
                    and all(record[k] == v for k, v in hashes.items())
                    and digest(record["proof"]) == record["proofDigest"]
                    and digest(record["finiteCertificate"]) == record["finiteDigest"]
                    and record["finiteCertificate"] and record["finiteCertificate"]["domain"] == spec["rows"]
                    and record["finiteCertificate"]["body"] == hashes):
                return {**record, "action": "exact reuse"}
        except (KeyError, TypeError, ValueError):
            pass
    feature = int(runtime_jdk.identity(jdk)["feature"])
    if any(runtime_jar.effective_class(f, name, feature) is not None
           for name in ("CheckedHelperUse", "CheckFinite") for f in files):
        raise ValueError("application class collides with the generated helper-proof harness")
    directory.mkdir(parents=True)
    java = directory/"CheckedHelperUse.java"
    java.write_text(source)
    main = directory/"CheckFinite.java"
    main.write_text("public class CheckFinite { public static void main(String[] args) {"
                    " for (int i=0; i<Integer.parseInt(args[0]); i++) if (!CheckedHelperUse.check(i))"
                    " throw new AssertionError(i); System.out.println(args[0]); } }")

    lemma = directory/"helper.contract"
    lemma.write_text(contract)
    cp = os.pathsep.join(str(f) for f in files)
    subprocess.run([jdk/"bin/javac", "-g", "-parameters", "-proc:none", "-cp", cp, "-d", directory, java, main],
                   check=True, capture_output=True, timeout=40)
    argv = [str(checker), "prove", "--classes", str(directory), "--classpath", cp, "CheckedHelperUse#check",
            "--assume", f"choice >= 0 && choice < {len(spec['rows'])}", "--assert", "result == true",
            "--engine", "native", "--gaps", "strict", "--unwind", "16", "--timeout", "60", "--json",
            "--lemmas", str(lemma)]
    env = {**os.environ, "JAVA_HOME": str(jdk), "PATH": str(jdk/"bin")+os.pathsep+os.environ["PATH"]}
    proc = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=75)
    if not proc.stdout.strip():
        raise ValueError("checked helper produced no verifier report: " + proc.stderr[-500:])
    proof = json.loads(proc.stdout)
    record = {"key": key, "qualification": rules, "entry": spec["entry"], "provider": origin, **hashes, "rows": spec["rows"],
              "contract": contract, "consumer": source, "argv": argv, "exit": proc.returncode,
              "proof": proof, "proofDigest": digest(proof)}
    # In an application trial the helper's JVM class is already initialized when its entry is reached.
    # Establish a second closed finite proof on that premise only for methods with no external operations.
    _, member, desc = runtime_jar.parse_target(spec["entry"])
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    _, code, handlers = declarations[member, desc]
    finite = None
    if handlers == 0 and local_integral_body(code, pool):
        ref = subprocess.run([jdk/"bin/java", "-verbose:class", "-cp", str(directory)+os.pathsep+cp,
                              "CheckFinite", str(len(spec["rows"]))], env=env, capture_output=True, text=True, timeout=35)
        from targets.upgrade_replay import class_origins
        loaded = class_origins(ref.stdout)
        if (ref.returncode == 0 and str(len(spec["rows"])) in ref.stdout.splitlines()
                and (origin == "java.base" or loaded.get(owner) == {Path(origin)})):
            finite = {"domain": spec["rows"], "body": hashes, "afterSuccessfulInitialization": True,
                      "provider": origin, "closedInstructions": [op for _, op in instructions(code)],
                      "normalReturns": len(spec["rows"]), "consumerClassSha256": sha(directory/"CheckedHelperUse.class")}
    record.update(finiteCertificate=finite, finiteDigest=digest(finite))
    native = proc.returncode == 0 and accepted(proof)
    refused = len(proof) == 1 and proof[0].get("verdict") == "unverifiable"
    if not finite or not (native or refused):
        return {**record, "action": "refused"}
    record["basis"] = "strict native lemma" if native else "closed integral bytecode and exhaustive JVM evaluation"
    if stored:
        change_evidence.write_json(stored, {"evidence": record, "sha256": digest(record)})
    return {**record, "action": "proved"}


def accepted(proof):
    if not isinstance(proof, list) or len(proof) != 1:
        return False
    row = proof[0]
    return (row.get("verdict") == "verified" and row.get("target") == "CheckedHelperUse#check"
            and any(a.get("kind") == "summary" and a.get("basis") == "proved"
                    for a in row.get("stated", {}).get("assumptions", [])))


def trace_config(directory, spec, proof):
    encode_hash = lambda key: base64.b64encode(bytes.fromhex(proof[key])).decode()
    lines = [spec["entry"], encode_hash("codeSha256"), encode_hash("poolSha256"), spec["callFrom"],
             spec["startupEntry"], spec["startupWithin"]]
    lines.extend(",".join(map(str, row["args"])) + "\t" + str(row["result"]) for row in spec["rows"])
    path = directory/"qualified-substitutions.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines)+"\n")
    return path


def applications(marks, loaded, spec, proof, files, arguments):
    """Require successful substitution on the original public path and its named startup witness."""
    from targets.upgrade_replay import sha
    if spec.get("requireAllApplications") and any(m.startswith("UPGRADE-UNCOVERED ") for m in marks):
        raise ValueError("a used helper tuple is outside the generated declaration")
    owner = spec["entry"].split("#")[0]
    if proof["provider"] != "java.base" and loaded.get(owner) != {Path(proof["provider"])}:
        raise ValueError("live helper did not come from its proved provider")
    caller = spec["callFrom"].split("#")[0]
    if not caller.startswith("java.") and len(loaded.get(caller, set()) & set(files)) != 1:
        raise ValueError("live consumer did not come from the ordered deployment")
    seen = [json.loads(base64.b64decode(m.split(" ", 1)[1])) for m in marks if m.startswith("UPGRADE-SUBSTITUTED ")]
    startup = [base64.b64decode(m.split(" ", 1)[1]).decode() for m in marks if m.startswith("UPGRADE-STARTUP ")]
    eligible = {(tuple(row["args"]), row["result"]) for row in proof["rows"]}
    if not seen or any((tuple(hit["args"]), hit["result"]) not in eligible or hit["caller"] != spec["callFrom"]
                       or hit["bci"] < 0 for hit in seen):
        raise ValueError("no applicable checked substitution on the registered observer history")
    startup_owner = spec["startupEntry"].split("#")[0]
    if not startup or (not startup_owner.startswith("java.") and len(loaded.get(startup_owner, set()) & set(files)) != 1):
        raise ValueError("missing original startup witness: " + spec["startupEntry"])
    resources = []
    name = spec.get("resource")
    if selector := spec.get("resourceByArgument"):
        name = selector["entries"].get(arguments[selector["index"]])
        if not name:
            raise ValueError("input has no registered startup resource")
    if name:
        for file in files:
            with zipfile.ZipFile(file) as jar:
                if name not in jar.namelist():
                    continue
                url = "file:" + file.as_posix() + "!/" + name
                if url in startup:
                    resources.append({"jar": sha(file), "entry": name, "sha256": hashlib.sha256(jar.read(name)).hexdigest()})
        if len(resources) != 1:
            raise ValueError("the live provider did not select the bound resource")
    return {"proofKey": proof["key"], "applications": seen, "startupEntry": spec["startupEntry"],
            "startupArguments": startup, "resources": resources}
