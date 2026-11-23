"""Run the documented comparison and independently inspect every freshly generated obligation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from prepare import HERE, HASHES

ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import array_induction


def run(number):
    folder, = (ROOT / "examples").glob(number + "-*")
    name = "Ints" if number == "336" else "Longs"
    compare = subprocess.run([sys.executable, "-B", "examples/tools/build.py", number, "--array-induction",
                              "first-any-length", "--compare"], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
    print(compare.stdout, end="")
    target = json.loads((folder / "target.json").read_text())
    spec, = [v for v in target["arrayContracts"] if v["id"] == "first-any-length"]
    with tempfile.TemporaryDirectory() as tmp:
        if not array_induction.run(folder, target, spec, 60, records=tmp):
            raise ValueError("fresh producer did not establish the request")
        src, = Path(tmp).glob("*/*/result.json")
        record = json.loads(src.read_text())
    answers = record["obligations"]
    assert record["status"] == "established" and all(a["expected"] == a["obtained"] for a in answers)
    assert [a["obtained"] for a in answers].count("unsat") == 8
    assert [a["obtained"] for a in answers].count("sat") == (2 if number == "336" else 3)
    assert record["classes"]["com/google/common/primitives/" + name]["sha256"] == HASHES[name]
    out = HERE / "evidence/baseline"
    out.mkdir(parents=True, exist_ok=True)
    (out / (number + ".json")).write_text(json.dumps({"compareExit": compare.returncode,
        "comparison":compare.stdout.splitlines(), "freshResult":record}, indent=2) + "\n")
    if compare.returncode != 0 or "the same result" not in compare.stdout:
        raise ValueError("fresh result differs from the historical comparison")


if __name__ == "__main__":
    run(sys.argv[1])
