"""Retain the complete public JSON observations when the normal receipt keeps only the prefix of a stream."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
import build
from targets import finite_oracle, interfaces, route, runtime, sidecar

PART_BYTES = 256 * 1024


def stream_entry(receipt, side):
    kept = "records/control-" + side + "-jdk21.stdout"
    entries = json.loads((receipt.parent / "records/streams.json").read_text())["streams"]
    entry, = (e for e in entries if e.get("kept") == kept and e["stream"] == "stdout")
    return entry


def checked_bytes(data, entry):
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("the complete observation stream differs from the original receipt")
    return data


def parts_directory(folder, entry):
    checksum = entry["sha256"]
    if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        raise ValueError("invalid observation stream digest")
    return folder / "records/public-observations" / checksum


def complete_stream(folder, receipt, side):
    entry = stream_entry(receipt, side)
    paths = sorted(parts_directory(folder, entry).glob("*.jsonl")) if entry["truncated"] else [receipt.parent / entry["kept"]]
    if not paths:
        raise ValueError(f"complete original JVM output needed for {folder.name} {side}: run public_observations.py {folder.name[:3]}")
    return checked_bytes(b"".join(p.read_bytes() for p in paths), entry), paths


def parts(lines):
    buf = bytearray()
    for line in lines:
        if len(line) > PART_BYTES:
            raise ValueError("one public JSON observation exceeds the part size")
        if len(buf) + len(line) > PART_BYTES:
            yield bytes(buf)
            buf.clear()
        buf.extend(line)
    if buf:
        yield bytes(buf)


def capture(number):
    folder, = build.EXAMPLES.glob(number + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    plan = route.resolve(folder, example, target, "replay")
    receipt = next(path for path in sorted((folder / "receipts/replay").glob("*/result.json"), reverse=True)
                   if json.loads(path.read_text())["conclusion"]["expectation"] == "yes")
    wanted = {s: stream_entry(receipt, s) for s in plan.revisions}
    if not any(e["truncated"] for e in wanted.values()):
        return
    table = finite_oracle.Table(folder / "controls/table.json")
    with tempfile.TemporaryDirectory(prefix="organic-public-rows-") as tmp:
        root = Path(tmp)
        prepared = {s: route.prepare_revision(plan, s, root / s, None) for s in plan.revisions}
        records = runtime.run_controls(plan, prepared, root / "controls")
        if isinstance(records, interfaces.Unsupported):
            raise ValueError(records.describe())
        for r in records:
            entry = wanted[r.revision]
            if not entry["truncated"]:
                continue
            if r.status != "exited" or r.exitCode != 0:
                raise ValueError(f"{r.revision} public driver did not complete")
            raw = checked_bytes((Path(r.directory) / r.stdout).read_bytes(), entry)
            lines = raw.splitlines(keepends=True)
            rows = [json.loads(line) for line in lines]
            differences = table.problems(rows)
            if (r.revision == "fix" and differences) or list(r.observations) != rows:
                raise ValueError("the public driver and the frozen observation table disagree")
            destination = parts_directory(folder, entry)
            destination.mkdir(parents=True, exist_ok=True)
            for i, chunk in enumerate(parts(lines)):
                path = destination / f"{i:04d}.jsonl"
                if path.exists() and path.read_bytes() != chunk:
                    raise ValueError("conflicting saved observation part")
                path.write_bytes(chunk)
            complete_stream(folder, receipt, r.revision)
            print(f"{number} {r.revision}: {len(rows)} original rows, {len(raw)} bytes, sha256 {entry['sha256']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    capture(parser.parse_args().example)
