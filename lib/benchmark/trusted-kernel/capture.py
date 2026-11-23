"""Record the actual bounded native calls, before selecting formulas for independent checking."""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from prepare import HERE, digest

ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import run as benchmark
sys.path.insert(0, str(ROOT / "examples/tools"))
import result_format


def save(transcripts, target):
    target.mkdir(parents=True, exist_ok=True)
    summaries = []
    for i, path in enumerate(sorted(transcripts.glob("*.icnf"))):
        raw = path.read_bytes()
        key = f"trace-{i}.icnf.gz"
        (target / key).write_bytes(gzip.compress(raw, mtime=0))
        counts = {answer: raw.count(f"c answer {answer} ".encode()) for answer in ("sat", "unsat", "unknown")}
        summaries.append({"file": key, "sha256": digest(raw), "answers": counts})
    return summaries


def main():
    target = HERE / "evidence/sat"
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        env = dict(os.environ, JVMCONTRACT_TRANSCRIPTS=str(tmp / "first"),
                   JVMCONTRACT_SOLVER="cadical")
        proc = subprocess.run([sys.executable, "examples/tools/build.py", "336", "--task", "first-8-release"],
                              cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(proc.stdout, end="")
        if proc.returncode or "as expected" not in proc.stdout:
            raise ValueError("original bounded task did not produce its expected receipt")
        receipt = proc.stdout.rsplit("receipt ", 1)[-1].strip()
        folder, = (ROOT / "examples").glob("336-*")
        result = json.loads((folder / receipt).read_text())
        if result_format.load(folder / receipt).get("matchesExpected") is not True or result["conclusion"]["status"] != "established":
            raise ValueError("bounded receipt is not qualified")
        first = save(tmp / "first", target / "first")
        record = {"336/first-8-release": first, "boundedReceipt": receipt,
                  "boundedConclusion": result["conclusion"], "checkerSha256": digest(Path(os.environ["JVMCONTRACT"]).read_bytes())}
        if not any(t["answers"]["unsat"] for t in first):
            case, = benchmark.load_cases([3], "held/prefix-sums")
            classes = {}
            for side in (case["before"],case["after"]):
                source = benchmark.HERE / benchmark.versions()[side]
                java, = source.rglob("PrefixSums.java")
                classes[side] = benchmark.javac([str(java)], tmp / side)
            work = tmp / "work"
            work.mkdir()
            opts = SimpleNamespace(jvmcontract=os.environ["JVMCONTRACT"], timeout=120, jbmc="jbmc")
            command = benchmark.command(case, "native", "strict", classes, work, opts)
            env["JVMCONTRACT_TRANSCRIPTS"] = str(tmp / "fallback")
            proc = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, check=True)
            data = json.loads(proc.stdout)
            if data["verdict"] != "verified":
                raise ValueError("prefix-sums workload did not verify")
            record["held/prefix-sums"] = save(tmp / "fallback", target / "fallback")
            record["fallbackSearch"] = data.get("search")
            if not any(t["answers"]["unsat"] for t in record["held/prefix-sums"]):
                raise ValueError("neither actual workload emitted UNSAT")
        (target / "capture.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({k:v for k,v in record.items() if "/" in k}))


if __name__ == "__main__":
    main()
