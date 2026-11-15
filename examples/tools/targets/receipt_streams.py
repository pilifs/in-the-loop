#!/usr/bin/env python3
"""What a target receipt keeps of its attempt's raw streams (workflow_ingest.py's records/, the user's review item 5 of
llm-dlc/loops/example-targets.md): each stage with how it ended, a not-started one's reason, and each bundled stream's
whole size and whether it was cut. Exits 1 when a stage's stdout or stderr, or the runner's records (controls.json for a
task with controls, verifier.json for a proof), isn't in the receipt's bundle, or when `--reason TEXT` is given and a
not-started stage's reason doesn't contain it (or no stage is not-started). Offline and read-only.

  python3 examples/tools/targets/receipt_streams.py RECEIPT_DIR [--reason TEXT]
  python3 examples/tools/targets/receipt_streams.py EXAMPLE_FOLDER TASK [--reason TEXT]   its latest receipt
"""

import argparse
import json
import sys
from pathlib import Path


def latest(folder, task):
    """The task's latest receipt directory: attempt ids sort in start order (workflow_ingest.publish)."""
    receipts = Path(folder) / "receipts" / task
    attempts = sorted(p for p in receipts.iterdir() if p.is_dir() and not p.name.startswith(".")) if receipts.is_dir() else []
    if not attempts:
        raise SystemExit(f"{receipts}: no receipt")
    return attempts[-1]


def problems(attempt, reason=None):
    """(lines describing the receipt's streams, problems): what check() prints and what makes it exit 1."""
    attempt = Path(attempt)
    document = json.loads((attempt / "result.json").read_text())
    listed = {a["path"] for a in (document.get("bundle") or {}).get("artifacts", [])}
    stages = (document.get("attempt") or {}).get("stages") or []
    try:
        streams = json.loads((attempt / "records/streams.json").read_text())["streams"]
    except (OSError, ValueError, KeyError) as e:
        return [], [f"records/streams.json can't be read: {e}"]
    lines = [f"{attempt}: {len(stages)} stages"]
    found = []
    for s in stages:
        lines.append(f"  {s['name']}: {s['status']}" + (f" (exit {s['exitCode']})" if s.get("exitCode") is not None else "")
                     + (f": {s['reason']}" if s.get("reason") else ""))
        for k in ("stdout", "stderr"):
            entry = next((e for e in streams if e.get("kept") == s[k]), None)
            if s[k] not in listed or entry is None:
                why = next((e.get("why") for e in streams if e.get("source") == s[k] and e.get("why")), None)
                found.append(f"{s['name']}'s {k} is not bundled ({s[k]}" + (f": {why})" if why else ")"))
                continue
            lines.append(f"    {k}: {s[k]}, {entry['bytes']} bytes" + (f", cut to {entry['keptBytes']}" if entry["truncated"] else ""))
    records = {e["kept"]: e for e in streams if e.get("stream") == "record" and e.get("kept")}
    wanted = (["records/controls.json"] if any(s["name"].startswith("jvm-control") for s in stages) else []) \
        + (["records/verifier.json"] if any(s["name"].startswith("verifier") for s in stages) else [])
    for name in wanted:
        if name not in records or name not in listed:
            found.append(f"{name} is not bundled")
        else:
            lines.append(f"  {name}: {records[name]['bytes']} bytes" + (", cut" if records[name]["truncated"] else ""))
    if reason is not None:
        idle = [s for s in stages if s["status"] == "not-started"]
        if not idle:
            found.append("no stage is not-started")
        found += [f"{s['name']}'s reason doesn't say {reason!r}: {s.get('reason')!r}" for s in idle
                  if reason not in (s.get("reason") or "")]
    return lines, found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("where", nargs="+", help="a receipt directory, or an example folder and a task")
    parser.add_argument("--reason", help="text every not-started stage's reason must contain")
    args = parser.parse_args(argv)
    if len(args.where) > 2:
        parser.error("give a receipt directory, or an example folder and a task")
    attempt = latest(*args.where) if len(args.where) == 2 else Path(args.where[0])
    lines, found = problems(attempt, args.reason)
    print("\n".join(lines))
    if found:
        print("receipt streams NOT bundled: " + "; ".join(found))
        return 1
    print("receipt streams bundled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
