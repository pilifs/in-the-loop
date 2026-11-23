"""Check reachable JVM witnesses against two original, unchanged historical verification conditions."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from prepare import HERE, digest

EV = HERE / "evidence"
FILL = (
    HERE.parents[2] / "examples/337-jdk-range-fill-alias/records/array-induction/"
    "caller-extra-any-length/98d5d5ae53cf2d12ce0c"
)
FRAME = EV / "transfer/frame/artifact.bin"
Z3 = "fcd0ca765d1c0b4eac776f442ec0f10294b9a6416be91fad4e52fa19012c8d01"


def read(path):
    return json.loads(path.read_bytes())


def guava_record():
    return next(row for row in read(EV / "transfer/results.json")["cases"] if row["control"] == "frame")


def regenerate_guava(dest):
    from controls import JDK

    sys.path.insert(0, str(HERE.parents[1] / "python"))
    import jvm_array_induction

    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        owner = tmp / "Ints.class"
        shutil.copyfile(FRAME, owner)
        proof = jvm_array_induction.prove(
            JDK / "bin/javap", owner, "indexOf", "([II)I", "first-index", tmp, 60
        )
    genuine = guava_record()["unchangedProducer"]
    if (
        proof.passed
        or proof.obligations != genuine["obligations"]
        or proof.solver != genuine["solver"]
        or digest(proof.smt.encode()) != genuine["formulaSha256"]
    ):
        raise ValueError("genuine Guava producer disagrees with the frozen rebound result")
    (dest / "guava.smt2").write_text(proof.smt)


def original_scope(original, pinned, obligations, obligation):
    if digest(original) != pinned:
        raise ValueError("original historical formula digest")
    unmet = [(i, o) for i, o in enumerate(obligations) if o["expected"] != o["obtained"]]
    if len(unmet) != 1 or unmet[0][1] != {"name": obligation, "expected": "unsat", "obtained": "sat"}:
        raise ValueError("unexpected original failing obligation")
    index = unmet[0][0]
    prelude, *blocks = re.split(r"(?m)^; VC (\d+)\n", original.decode())
    if list(map(int, blocks[::2])) != list(range(len(obligations))):
        raise ValueError("incomplete original query inventory")
    block = blocks[2 * index + 1]
    if not re.fullmatch(r"\(push 1\)\n\(assert [^\n]+\)\n\(check-sat\)\n\(pop 1\)\n", block):
        raise ValueError("unexpected original solver scope")
    return index, prelude, block


def witness_query(prelude, block, bindings):
    # Add only input equalities before the original, byte-for-byte solver scope.
    return prelude + "".join(f"(assert {expr})\n" for expr in bindings) + block


def replay(z3, original, pinned, obligations, obligation, inputs):
    index, prelude, block = original_scope(original, pinned, obligations, obligation)
    rows = []
    for name, bindings, expected in inputs:
        query = witness_query(prelude, block, bindings)
        answer = subprocess.run(
            [z3, "-in", "-smt2"], input=query, text=True, capture_output=True, check=True, timeout=30
        ).stdout.strip()
        if answer != expected:
            raise ValueError((name, answer, expected))
        rows.append(
            {
                "control": name,
                "bindings": bindings,
                "expected": expected,
                "actual": answer,
                "querySha256": digest(query.encode()),
            }
        )
    return {
        "originalFormulaSha256": pinned,
        "zeroBasedQuery": index,
        "originalScopeSha256": digest(block.encode()),
        "obligation": obligation,
        "historicalStatus": "unresolved",
        "controls": rows,
    }


def report(folder):
    z3 = shutil.which("z3")
    if not z3 or digest(Path(z3).read_bytes()) != Z3:
        raise ValueError("expected the baseline Z3 executable")
    guava = guava_record()
    old = guava["unchangedProducer"]
    fill = read(FILL / "result.json")
    if (
        digest(FRAME.read_bytes()) != guava["classSha256"]
        or fill["status"] != "unresolved"
        or fill["solver"]["sha256"] != Z3
        or old["solver"]["sha256"] != Z3
    ):
        raise ValueError("historical control binding")
    search_input = ["(= length #x00000001)", "(= cursor #x00000000)", "(= k #x00000000)", "(= heap initial)"]
    call_input = [
        "(= length #x00000001)",
        "(= from #x00000000)",
        "(= to #x00000000)",
        "(= value #x00000007)",
        "(= (select initial #x00000000) #x0000000b)",
    ]
    search = replay(
        z3,
        (folder / "guava.smt2").read_bytes(),
        old["formulaSha256"],
        old["obligations"],
        "preserve the input heap",
        [
            (
                "changing-store",
                search_input + ["(= target #x00000007)", "(= (select initial k) target)"],
                "sat",
            ),
            (
                "same-value-store",
                search_input + ["(= target #x00000000)", "(= (select initial k) target)"],
                "unsat",
            ),
        ],
    )
    caller = replay(
        z3,
        (FILL / "obligations.smt2").read_bytes(),
        fill["certificateSha256"],
        fill["obligations"],
        "caller read follows from the proved frame",
        [
            (
                "shared-empty-range",
                call_input
                + [
                    "(= aliases true)",
                    "(= k #x00000000)",
                    "(= otherLength length)",
                    "(= otherInitial initial)",
                ],
                "sat",
            ),
            (
                "distinct-valid-observation",
                call_input
                + [
                    "(= aliases false)",
                    "(= k #x00000001)",
                    "(= otherLength #x00000002)",
                    "(= (select otherInitial k) #x0000001f)",
                ],
                "unsat",
            ),
        ],
    )
    range_rows = read(EV / "range-proof/results.json")["cases"]
    extra = next(row for row in range_rows if row["control"] == "caller-extra-any-length")
    if (
        "frame changed, return 0, after [0]" not in guava["outcome"]
        or "returned 7, after [7], expected 11 and [11]" not in extra["reason"]
        or extra["classSha256"] != fill["classes"]["fill/Range"]["sha256"]
    ):
        raise ValueError("byte-bound witness differs")
    for result, source, reason in [(search, guava, guava["outcome"]), (caller, extra, extra["reason"])]:
        result.update(
            classSha256=source["classSha256"],
            checkerVersion=source["checkerVersion"],
            independentWitness=reason,
        )
    return {
        "schema": "historical-concrete-frame/v1",
        "solverSha256": Z3,
        "source": "Original solver obligations restricted to fixed inputs. Each full verification condition is retained.",
        "cases": [search, caller],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", type=Path)
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args()
    folder = args.record or EV / "frame-witness"
    if args.record:
        folder.mkdir(parents=True, exist_ok=True)
        regenerate_guava(folder)
    data = report(folder)
    dest = folder / "results.json"
    if args.record:
        dest.write_text(json.dumps(data, indent=2) + "\n")
    elif data != read(dest):
        raise ValueError("concrete obligation replay differs")
    print([(r["obligation"], [(c["control"], c["actual"]) for c in r["controls"]]) for r in data["cases"]])
