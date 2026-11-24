"""Check the decisions of the compiled range rule and two byte-bound forward edges in Lean."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import tempfile

from frozen_range import KERNEL_PATH
from prepare import HERE, digest
from range_qualification import extract_arrays
from replay import LEAN, build_kernel, contained, measured

PHASES = ("guard", "entry", "exhausted", "iteration")
TERMS = ("zero", "lo", "cursor", "hi", "len")
TESTS = ("eq", "ne", "lt", "ge", "gt", "le")
SPECS = ("([IIII)V", "([JIIJ)V")


def exporter(folder, mutated=False):
    src = folder / KERNEL_PATH
    src.mkdir(parents=True)
    sources = {}
    for path in sorted(HERE.rglob("*.rs")):
        rel = path.relative_to(HERE)
        data = path.read_bytes()
        if mutated and rel.as_posix() == "range.rs":
            marker = b"    if let (Int(x), Int(y)) = (a, b) {"
            if data.count(marker) != 1:
                raise ValueError("ambiguous branch-rule control location")
            data = data.replace(marker, b"    if phase == Phase::Guard && a == From && b == To && matches!(test, Test::Lt) { return Ok(true); }\n" + marker)
        dst = src / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        sources[str(rel)] = digest(data)
    shared = src / "../../src/digest.rs"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / "../../src/digest.rs", shared)
    sources["../../src/digest.rs"] = digest(shared.read_bytes())
    binary = folder / "export"
    build = measured(["rustc", "--test", "--edition=2021", "-C", "opt-level=2", "-C",
                      "target-feature=+crt-static", "-C", "strip=symbols", "main.rs", "-o", binary], src)
    if build["exit"]:
        raise ValueError(build)
    return binary, {"build": build, "binarySha256": digest(binary.read_bytes()), "sources": sources}


def export(binary, artifact, tmp):
    tmp.mkdir()
    shutil.copy2(binary, tmp / "export")
    (tmp / "Arrays.class").write_bytes(artifact)
    run = contained(["./export", "--nocapture", "--test-threads=1"], tmp)
    if run["exit"]:
        raise ValueError(run)
    rows, edges = {}, {}
    for line in run["stdout"].splitlines():
        if "DECISION " in line:
            phase, x, y, op, result = line.split("DECISION ")[1].split()
            key = (phase, x, y, op)
            if key in rows or result not in {"true", "false", "open"}:
                raise ValueError(line)
            rows[key] = result
        if line.startswith("EDGE "):
            desc, slot, body, answer = line[5:].split(" ", 3)
            edges[desc] = {"slot": int(slot), "code": body, "rust": answer}
    expected = {(p, x, y, t) for p in PHASES for x in TERMS for y in TERMS for t in TESTS}
    if set(rows) != expected or set(edges) != set(SPECS):
        raise ValueError("incomplete compiled export")
    return rows, edges


def lean(folder, additions):
    folder.mkdir()
    core = (HERE / "RangeRule.lean").read_text()
    module = core + "\nopen RangeRule\n" + additions
    (folder / "Check.lean").write_text(module)
    result = contained([str(LEAN / "bin/lean"), "Check.lean"], folder,
                       [LEAN, "/usr/lib", "/lib64", "/dev/urandom"])
    return {"sha256": digest(module.encode()), **result}


def lemma(key, value, name):
    phase, x, y, op = key
    return (f"theorem {name} : sound .{phase} .{x} .{y} .{op} {value} := by\n"
            "  unfold sound\n  intro lo i hi n bounds\n"
            "  simp [admitted] at bounds\n  simp [RangeRule.compare, RangeRule.term] <;> omega\n")


def backedge(desc, body, name):
    wide = "true" if desc == SPECS[1] else "false"
    code = str(list(bytes.fromhex(body)))
    return (f"def {name}Code : List Nat := {code}\n"
            f"theorem {name}Decoded : forwardBody {wide} {name}Code = true := by decide\n"
            f"theorem {name}Step (old now : Int → α) (v : α) (lo i hi n : Int)\n"
            "    (bounds : admitted .iteration lo i hi n) (pre : prefixFrame old now lo i v) :\n"
            f"    ∃ after j, step {wide} {name}Code now i v = some (after, j) ∧ "
            "prefixFrame old after lo j v ∧ j = i + 1 ∧ j ≤ 2147483647 ∧ "
            "0 ≤ hi - j ∧ hi - j < hi - i :=\n"
            f"  iteration {wide} {name}Code {name}Decoded old now v lo i hi n bounds pre\n"
            f"#print axioms {name}Step\n")


def qualify(tmp):
    if digest((LEAN / "bin/lean").read_bytes()) != "db7f559d05795e7af52e42bc966c90240a39dcb9712161c54c97afa546e20c00":
        raise ValueError("Lean 4.36.0 executable binding")
    arrays = extract_arrays(tmp / "Arrays.bin").read_bytes()
    current = tmp / "current"
    current.mkdir()
    _, production = build_kernel(current)
    binary, build = exporter(tmp / "good")
    rows, edges = export(binary, arrays, tmp / "original")
    counts = Counter(rows.values())
    if counts != {"true": 168, "false": 168, "open": 264}:
        raise ValueError(counts)
    body = []
    for i, (key, value) in enumerate(sorted(rows.items())):
        if value != "open":
            body.append(lemma(key, value, f"decision_{i}"))
            body.append(f"#print axioms decision_{i}\n")
    for desc, name in zip(SPECS, ("intFill", "longFill")):
        if edges[desc]["rust"] != "accepted 37 " + digest(arrays):
            raise ValueError(edges[desc])
        body.append(backedge(desc, edges[desc]["code"], name))
    good = lean(tmp / "good-lean", "".join(body))
    output = good["stdout"].splitlines()
    axioms = [line for line in output if "depends on axioms:" in line or "does not depend on any axioms" in line]
    if good["exit"] or len(axioms) != 338 or any("sorryAx" in line for line in axioms):
        raise ValueError((good["exit"], output[-25:], [line for line in output if "error:" in line][:5]))
    good["axioms"] = dict(Counter(line.partition("depends on axioms: ")[2] or "none" for line in axioms))
    good.pop("stdout")

    broken, changed_build = exporter(tmp / "changed", mutated=True)
    bad_rows, _ = export(broken, arrays, tmp / "changed-export")
    differences = {key: (rows[key], bad_rows[key]) for key in rows if rows[key] != bad_rows[key]}
    wrong = ("guard", "lo", "hi", "lt")
    if differences != {wrong: ("open", "true")}:
        raise ValueError(differences)
    rejected = lean(tmp / "bad-lean", lemma(wrong, "true", "badStrictGuard"))
    if not rejected["exit"] or "error:" not in rejected["stdout"]:
        raise ValueError("Lean proved the strict-guard control")

    controls = {}
    for label, pos, opcode in [("index-local", 18, 1), ("value-local", 19, 28)]:
        original = bytes.fromhex(edges[SPECS[0]]["code"])
        if arrays.count(original) != 1:
            raise ValueError("ambiguous original int range body")
        changed = bytearray(original)
        changed[pos] = opcode
        rebound = arrays.replace(original, changed)
        _, altered = export(binary, rebound, tmp / label)
        edge = altered[SPECS[0]]
        if edge["code"] != changed.hex() or "at store 20" not in edge["rust"]:
            raise ValueError(edge)
        bad_link = lean(tmp / (label + "-lean"), backedge(SPECS[0], edge["code"], "altered"))
        if not bad_link["exit"] or "error:" not in bad_link["stdout"]:
            raise ValueError("Lean accepted the rebound back edge")
        controls[label] = {"classSha256": digest(rebound), "code": edge, "lean": bad_link}
    return {"schema": "range-rule-correspondence/v1", "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
            "environment": "Verified initialized classes; signed Java indices from 0 to Integer.MAX_VALUE.",
            "classSha256": digest(arrays), "compiler": build, "production": production,
            "leanExecutable": digest((LEAN / "bin/lean").read_bytes()),
            "proofSource": digest((HERE / "RangeRule.lean").read_bytes()), "lean": good,
            "table": [{"phase": p, "left": x, "right": y, "comparison": op, "decision": v}
                      for (p, x, y, op), v in sorted(rows.items())],
            "counts": counts, "edges": edges,
            "strictGuardControl": {"compiler": changed_build, "row": wrong, "valuation": [0, 0, 0, 0],
                                   "lean": rejected}, "edgeControls": controls}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        result = qualify(Path(td))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["counts"], result["lean"]["axioms"], list(result["edgeControls"]))
