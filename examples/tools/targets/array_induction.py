"""Array induction for the examples: the adapter between an example's declared array contract and the proof method.

The method itself is lib/python/jvm_array_induction.py (the walk over the compiled control-flow graph, each rule's
obligations, the solver's answers): it takes a bound method and a rule, and knows no example. This module finds the
example and its contract, takes the revision the contract names, prepares its artifacts, loads the classes by the
prepared class path, refuses a class whose initializer the rule does not qualify, and publishes the record.

    python3 examples/tools/build.py NNN --array-induction CONTRACT

A record names the rule implementation it was made by under `rules`: each file of the method and this one, by
digest. Records from before the method moved (`java-array-induction-result/v1`) have `rulesSha256` instead, the
digest of this one file as it then was, when it held the method too.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

import jvm_array_induction as core  # noqa: E402  (lib/python, on the path through this package)
# The names other modules have always taken from here: the disassembly reader (the schedule and monitor experiments)
# and the method's own.
from jvm_array_induction import Induction, Instruction, State, methods, range_caller, solve  # noqa: E402,F401

from targets import interfaces, route, runtime, runtime_jar, runtime_jdk, sidecar, workflow  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def record_key(folder, target, contract):
    example = json.loads((folder / "example.json").read_text())
    plan = route.resolve(folder, example, target, contract["bindingTask"])
    if (
        isinstance(plan, interfaces.Unsupported)
        or len(plan.revisions) != 1
        or plan.revisions[0] != contract["revision"]
    ):
        raise ValueError("the public artifact-binding task cannot supply the selected revision")
    locked = runtime.lock(plan, contract["revision"])
    if isinstance(locked, interfaces.Unsupported) or locked.stage != "source-locked":
        raise ValueError("the array contract has no current source lock")
    declaration = {
        "schema": "java-array-induction/v1",
        "contract": contract,
        "source": locked.source,
        "commit": locked.commit,
        "lengths": "all already allocated non-null Java arrays",
        "indexArithmetic": "signed 32-bit Java operations",
        "heap": "primitive long cells" if contract["entry"].endswith("([JJ)I") else "primitive int cells",
    }
    return plan, workflow.canonical_digest(declaration)


def evidence(folder, target, task):
    out = []
    for spec in target.get("arrayContracts", []):
        if spec["bindingTask"] != task:
            continue
        _, key = record_key(folder, target, spec)
        records = []
        for path in sorted((folder / "records/array-induction" / spec["id"]).glob("*/result.json")):
            doc = json.loads(path.read_text())
            if doc.get("sourceKey") != key:
                continue
            certificate = path.parent / "obligations.smt2"
            disassembly = path.parent / "class.javap"
            answers = doc.get("obligations", [])
            passed = bool(answers) and all(v["expected"] == v["obtained"] for v in answers)
            if (
                certificate.is_file()
                and runtime.sha256(certificate) == doc["certificateSha256"]
                and disassembly.is_file()
                and runtime.sha256(disassembly) == doc["disassemblySha256"]
                and doc["status"] == ("established" if passed else "unresolved")
            ):
                records.append({"status": doc["status"], "record": str(path.relative_to(folder))})
        out.append(
            {
                "id": spec["id"],
                "rule": spec["rule"],
                "sourceKey": key,
                "lengths": "all allocated",
                "records": records,
            }
        )
    return out


def run(folder, target, spec, seconds, records=None):
    """Prove one declared contract and publish its record under the example's records, or under `records` when
    given (a comparison that must not add to the example)."""
    plan, source_key = record_key(folder, target, spec)
    result_root = (Path(records) if records else folder / "records/array-induction") / spec["id"]
    (feature,) = next(a for a in plan.artifacts if a["revision"] == spec["revision"])["jdks"]
    home = Path(runtime_jdk.home(feature))
    jmod = home / "jmods/java.base.jmod"
    owner, name, descriptor = runtime_jar.parse_target(spec["entry"])
    with tempfile.TemporaryDirectory(prefix="java-array-induction-") as directory:
        work = Path(directory)
        prepared = route.prepare_revision(plan, spec["revision"], work / "prepare", {})
        if isinstance(prepared, interfaces.Unsupported) or prepared.stage != "artifacts-ready":
            raise ValueError("artifact preparation failed: " + str(prepared))
        entries = runtime._checked(work / "prepare", prepared)
        paths = [work / "prepare" / a.path for a in entries if a.role in ("original", "dependency")]
        classes = {}

        def load(cls):
            if cls.startswith("java/"):
                with zipfile.ZipFile(jmod) as image:
                    data = image.read("classes/" + cls + ".class")
                origin = "java.base"
            else:
                matches = [
                    (path, data) for path in paths if (data := runtime_jar.read_class(path, cls)) is not None
                ]
                if len(matches) != 1:
                    raise ValueError(f"expected one selected definition of {cls}")
                path, data = matches[0]
                origin = str(path.relative_to(work / "prepare"))
            if runtime_jar.this_class(data) != cls:
                raise ValueError("class bytes identify a different class")
            classes[cls] = {"sha256": hashlib.sha256(data).hexdigest(), "origin": origin}
            return data

        cls = owner.replace(".", "/")
        data = load(cls)
        class_file = work / (cls.split("/")[-1] + ".class")
        class_file.write_bytes(data)
        disassembled = methods(home / "bin/javap", class_file)
        code = disassembled[0]
        if cls.startswith("java/"):
            # Arrays' only initializer on this image records the class's assertion switch.
            init = code.get(("<clinit>", "()V"), {}).get("code", [])
            if (
                [i.op for i in init]
                != ["ldc", "invokevirtual", "ifne", "iconst_1", "goto", "iconst_0", "putstatic", "return"]
                or init[0].member != "class " + cls
                or init[1].member != "Method java/lang/Class.desiredAssertionStatus:()Z"
                or int(init[2].arg) != init[5].pc
                or int(init[4].arg) != init[6].pc
                or init[6].member != "Field $assertionsDisabled:Z"
                or runtime_jar.super_class(data) != "java/lang/Object"
                or runtime_jar.interfaces(data)
            ):
                raise ValueError("unqualified platform initializer")
        else:
            seen = set()
            pending = [cls]
            while pending:
                cursor = pending.pop()
                if cursor in seen or cursor == "java/lang/Object":
                    continue
                seen.add(cursor)
                parent_data = data if cursor == cls else load(cursor)
                if ("<clinit>", "()V") in runtime_jar.methods(parent_data):
                    raise ValueError(f"unqualified reachable initializer on {cursor}")
                pending.extend(runtime_jar.interfaces(parent_data))
                parent = runtime_jar.super_class(parent_data)
                if parent:
                    pending.append(parent)
        caller, caller_evidence = spec.get("caller"), None
        bound_caller = None
        if caller:
            caller_owner, caller_name, caller_descriptor = runtime_jar.parse_target(caller)
            caller_data = load(caller_owner.replace(".", "/"))
            if (
                caller_descriptor != "([I[IIIII)I"
                or ("<clinit>", "()V") in runtime_jar.methods(caller_data)
                or runtime_jar.super_class(caller_data) != "java/lang/Object"
                or runtime_jar.interfaces(caller_data)
            ):
                raise ValueError("unqualified caller descriptor or initializer")
            caller_file = work / (caller_owner.split(".")[-1] + ".class")
            caller_file.write_bytes(caller_data)
            bound_caller = (caller_file, caller_name, caller_descriptor)
        proof = core.prove(home / "bin/javap", class_file, name, descriptor, spec["rule"], work, seconds,
                           owner=cls, caller=bound_caller, disassembled=disassembled)
        if caller:
            caller_evidence = {
                "entry": caller,
                "classSha256": classes[caller_owner.replace(".", "/")]["sha256"],
                "callee": spec["entry"],
                "calleeClassSha256": classes[cls]["sha256"],
                **proof.caller,
                "roots": "the same int array or two distinct int arrays of independent legal lengths",
            }
        smt, obligations, solver, disassembly = proof.smt, proof.obligations, proof.solver, proof.disassembly
        passed = proof.passed
        cp = [
            {"path": a.path, "role": a.role, "sha256": a.sha256}
            for a in entries
            if a.role in ("original", "dependency")
        ]
        result = {
            "schema": "java-array-induction-result/v2",
            "sourceKey": source_key,
            "entry": spec["entry"],
            "revision": spec["revision"],
            "rule": spec["rule"],
            "status": "established" if passed else "unresolved",
            "domain": f"Every non-null, already allocated {'long' if proof.cell_bits == 64 else 'int'} array of legal Java length and all signed scalar inputs"
            + (" with 0 <= from <= to <= length." if spec["rule"] == "range-fill" else "."),
            "preparation": prepared.commit,
            "classpath": cp,
            "classes": classes,
            "jdk": runtime_jdk.identity(home),
            # The rule implementation: the method's files and this adapter, which qualifies the initializers.
            "rules": core.implementation(extra=[__file__], root=REPO),
            "heapCellBits": proof.cell_bits,
            "indexBits": proof.index_bits,
            "javapSha256": runtime.sha256(home / "bin/javap"),
            "solver": solver,
            "solverTimeoutSeconds": seconds,
            "bytecode": proof.trace,
            "obligations": obligations,
            "certificateSha256": hashlib.sha256(smt.encode()).hexdigest(),
            "disassemblySha256": hashlib.sha256(disassembly.encode()).hexdigest(),
        }
        if caller_evidence:
            result["caller"] = caller_evidence
        record_id = workflow.canonical_digest(result)[:20]
        dest = result_root / record_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "obligations.smt2").write_text(smt)
        (dest / "class.javap").write_text(disassembly)
        (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        shown = dest.relative_to(folder) if folder in dest.parents else dest
        print(f"{spec['id']}: {result['status']}, {len(obligations)} solver answers, {shown}")
        return passed


# What a second run of a contract must repeat to be the same result, and what only describes the machine it ran on.
CLAIM_FIELDS = ("sourceKey", "entry", "revision", "rule", "status", "domain", "preparation", "classpath", "classes", "heapCellBits",
                "indexBits", "bytecode", "obligations", "certificateSha256", "caller")
MACHINE_FIELDS = ("jdk", "javapSha256", "solver", "solverTimeoutSeconds", "disassemblySha256")


def rules_of(doc):
    """The rule implementation a record names, in one shape for both formats: {"files": {path: sha256}, "sha256"}.
    A v1 record's `rulesSha256` is the digest of this one file as it was when it held the method too, and it stays
    that: it is given as that file's digest, with no combined digest, since none was recorded."""
    if isinstance(doc.get("rules"), dict):
        return doc["rules"]
    if isinstance(doc.get("rulesSha256"), str):
        return {"files": {"examples/tools/targets/array_induction.py": doc["rulesSha256"]}, "sha256": None}
    return None


def differences(new, stored):
    """The fields in which two records of one contract differ: (those that are the result, those that describe the
    machine). A field only one of them has is a difference."""
    absent = object()
    differs = lambda fields: [k for k in fields if new.get(k, absent) != stored.get(k, absent)]
    return differs(CLAIM_FIELDS), differs(MACHINE_FIELDS)


def compare(folder, target, spec, seconds):
    """Prove one declared contract again, into a scratch folder, and compare it with the example's stored records of
    the same contract and source: True when the newest format's record is repeated in every field that is the
    result (the named obligations with their expected and obtained answers, the widths, the class digests, the
    bytecode walked, the status, so an unresolved negative control must be unresolved on the same obligation).
    Nothing is written to the example."""
    with tempfile.TemporaryDirectory() as scratch:
        run(folder, target, spec, seconds, records=scratch)
        (path,) = (Path(scratch) / spec["id"]).glob("*/result.json")
        new = json.loads(path.read_text())
    stored = [(p, json.loads(p.read_text())) for p in sorted((folder / "records/array-induction" / spec["id"]).glob("*/result.json"))]
    same_source = [(p, d) for p, d in stored if d.get("sourceKey") == new["sourceKey"]]
    full = [(p, d) for p, d in same_source if all(k in d for k in ("heapCellBits", "indexBits"))]
    if not full:
        print(f"{spec['id']}: no stored record of this source in the current format to compare with ({len(stored)} stored)")
        return False
    unmet = [(o["name"], o["expected"], o["obtained"]) for o in new["obligations"] if o["expected"] != o["obtained"]]
    repeated = False
    for p, d in full:
        result, machine = differences(new, d)
        repeated = repeated or not result
        print(f"{spec['id']}: {new['status']}, {len(new['obligations'])} solver answers, cells {new['heapCellBits']} bits, "
              f"indices {new['indexBits']} bits; against {p.parent.relative_to(folder)}: "
              + ("the same result" if not result else "differs in " + ", ".join(result))
              + (f"; the machine differs in {', '.join(machine)}" if machine else ""))
    for name, want, got in unmet:
        print(f"{spec['id']}: unmet: {name}: expected {want}, obtained {got}")
    made_by = new["rules"]
    print(f"{spec['id']}: rule implementation {made_by['sha256'][:16]} over {', '.join(made_by['files'])}")
    return repeated


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("contract")
    parser.add_argument("--checker-seconds", type=int, default=60)
    parser.add_argument("--compare", action="store_true",
                        help="prove into a scratch folder and compare with the stored record: exit 0 when the result is "
                             "repeated, whatever its status, and write nothing to the example")
    args = parser.parse_args(argv)
    import build

    (folder,) = build.EXAMPLES.glob(args.example + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    matches = [spec for spec in target.get("arrayContracts", []) if spec["id"] == args.contract]
    if len(matches) != 1 or args.checker_seconds <= 0:
        parser.error("expected one declared array contract and a positive solver deadline")
    try:
        if args.compare:
            return 0 if compare(folder, target, matches[0], args.checker_seconds) else 1
        return 0 if run(folder, target, matches[0], args.checker_seconds) else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"{args.contract}: unresolved: {exc}")
        return 1
