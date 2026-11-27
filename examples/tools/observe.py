#!/usr/bin/env python3
"""Two reports on a change's public behaviour, for whoever prepares it.

    observe.py startup-facts RECORD
        an original property and its separately scoped startup retry, from a startup claim report
        (examples/tools/targets/startup_facts.py writes one)
    observe.py public-observation URL [--packet DIR] --work DIR [--measure]
        freeze, or with --measure measure, the public behaviour of a merged pull request from its original
        deployment packet (examples/tools/targets/public_observation.py); prints the review as JSON

Until 2026-11-27 these were two commands of `watch.py`, the proof run's watcher, which is retired
(llm-dlc/retired.md). They never had to do with watching a run: each only calls the module named beside it.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("startup-facts", help="show an original property and its separately scoped startup retry").add_argument("record", type=Path)
    public = sub.add_parser("public-observation",
                            help="freeze or measure public behavior from a merged PR and its original deployment packet")
    public.add_argument("url")
    public.add_argument("--packet", type=Path)
    public.add_argument("--work", type=Path, required=True)
    public.add_argument("--measure", action="store_true")
    args = ap.parse_args(argv)
    if args.command == "public-observation":
        from targets import public_observation
        print(json.dumps(public_observation.watch(args.url, args.packet, args.work.resolve(), args.measure), indent=2))
        return 0
    from targets.startup_facts import summary
    report = json.loads(args.record.read_bytes())
    if report.get("schema") != "startup-claim-report/v1":
        ap.error("expected a startup claim report")
    print(summary(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
