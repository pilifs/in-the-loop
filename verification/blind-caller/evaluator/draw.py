"""Draw from the two committed freezes. Prints only per-batch counts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from eligibility_inventory import HERE, ROOT, digest, read, relative, write


def rank(seed, *components):
    return hashlib.sha256(seed + b"".join(b"\0" + s.encode() for s in components)).hexdigest()


def choose(roster, policy):
    seed = bytes.fromhex(policy["seedHex"])
    out = []
    for batch, size in policy["sample"].items():
        rows = [r for r in roster if r["eligible"] and r["batch"] == batch]
        def pr_order(r):
            return rank(seed, "PR", batch, r["canonicalPR"], r["pins"]["parent"], r["pins"]["fix"]), r["canonicalPR"]
        ranked = sorted(rows, key=pr_order)
        if batch == "R":
            repos = sorted({r["repository"] for r in ranked}, key=lambda p: (rank(seed, "project", batch, p), p))
            first = {}
            for row in ranked:
                first.setdefault(row["repository"], row)
            ranked = [first[p] for p in repos]
        if len(ranked) < size:
            raise ValueError("insufficient eligible population")
        out.extend(ranked[:size])
    if len({r["canonicalPR"] for r in out}) != len(out):
        raise ValueError("duplicate selected PR")
    return out


def committed(revision, path):
    if not re.fullmatch("[a-f0-9]{40}", revision):
        raise ValueError("a full committed Git object name is required")
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{path}"], stderr=subprocess.PIPE)


def seal(prereg, producer, policy_path, destination):
    evidence = []
    for name in ("protocol.json", "eligibility.json", "draw.py", "eligibility_inventory.py"):
        path = HERE / name
        if committed(prereg, relative(path)) != path.read_bytes():
            raise ValueError("eligibility or rule differs from its committed preregistration")
        evidence.append({"path": relative(path), "sha256": digest(path)})
    if Path(policy_path).is_absolute() or ".." in Path(policy_path).parts:
        raise ValueError("expected a committed repository-relative producer policy")
    freeze = []
    for path in (policy_path, "examples/tools/targets/blind_prediction.py", "examples/tools/targets/blind_measure.py"):
        blob = committed(producer, path)
        if not blob:
            raise ValueError("empty producer source or policy")
        freeze.append({"path": path, "sha256": hashlib.sha256(blob).hexdigest()})
    rows = choose(read(HERE / "eligibility.json")["rows"], read(HERE / "protocol.json"))
    draw = {"schema": "blind-caller-draw/v1", "preregistration": prereg, "producerRevision": producer,
            "preregistrationFiles": evidence, "producerFiles": freeze,
            "cases": [{k: r[k] for k in ("number", "slot", "batch", "url", "repository", "pins", "priorProjectSeen", "sharedApiPackages")}
                      for r in rows]}
    if destination.exists() and read(destination) != draw:
        raise ValueError("a different draw is already sealed")
    write(destination, draw)
    print(json.dumps(dict(Counter(r["batch"] for r in rows))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration", required=True)
    parser.add_argument("--producer", required=True)
    parser.add_argument("--producer-policy", required=True)
    parser.add_argument("--output", type=Path, default=HERE / "draw.json")
    args = parser.parse_args()
    seal(args.preregistration, args.producer, args.producer_policy, args.output)
