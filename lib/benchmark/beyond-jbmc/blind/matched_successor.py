"""Requalify the original matched native questions after the namespace fix, using unchanged JBMC records."""
import argparse
import os
from pathlib import Path

from evaluate_panel import matched_namespace
from packets import BASE
from scaffold_first import DEST, HERE, OUTPUT, compressed, digest, read, registered, save
from history import ROOT


def repeat(slot, output_root):
    _, ref, spec, _, _ = registered(slot)
    scaffold = compressed(DEST / "scaffolds" / (slot + ".json.gz"))
    if scaffold["firstScaffoldStop"]:
        raise ValueError("physical registration incomplete")
    old_pair = read(OUTPUT / "blind" / slot / "matched/report.json")
    separate = old_pair["status"] != "measured"
    previous = OUTPUT / "blind" / slot / ("assisted" if separate else "matched")
    out = output_root / slot
    out.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    exit_code = matched_namespace(BASE / slot / "packet", ref, out, checker, False,
                                  "assisted_worker.py" if separate else "matched_worker.py", native_only=True)
    worker = read(out / "worker.json")
    if exit_code or worker["status"] != "measured":
        raise ValueError(f"{slot}: original matched preparation stopped: {worker.get('failure',worker['status'])}")
    rows = []
    for label in (("old", "new") if separate else ("comparison",)):
        earlier = compressed(previous / label / "results.json.gz")
        result = compressed(out / label / "results.json.gz")
        if len(result["rows"]) != 3 or result["jvm"]["checks"] != earlier["jvm"]["checks"]:
            raise ValueError("original control or property population differs")
        for old, new in zip(earlier["rows"], result["rows"], strict=True):
            if old["method"] != new["method"] or old["expected"] != new["expected"]:
                raise ValueError("different original property")
            rows.append({"deployment": label, "method": new["method"], "scope": spec["domain"],
                         "old": old["native"], "new": new["native"]})
    save(out / "summary.json", {"job": os.environ.get("VERIFY_JOB_ID"), "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
         "checkerSha256": digest(checker), "basis": "original release conjuncts" if separate else "original matched two-copy caller",
         "physicalRegistration": digest(DEST / "scaffolds" / (slot + ".json.gz")), "rows": rows})
    print(slot, [(r["deployment"], r["method"], r["new"].get("verdict")) for r in rows], flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slots", nargs="+")
    ap.add_argument("--output", type=Path, default=DEST / "matched-native")
    args = ap.parse_args()
    for slot in args.slots:
        repeat(slot, args.output)
