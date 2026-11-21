"""Reproduce the published CompSuite/CompCheck overlap from two pinned files."""

import argparse
import hashlib
import json
from pathlib import Path


COMPSUITE = {
    "url": "https://raw.githubusercontent.com/compsuite-team/compsuite/"
           "6e6d738c8b0ca6ecbba6220b1fd549b2ae14a05d/incompatibilities.json",
    "sha256": "e8e7aa62119590e358a3a59f4f49e223f9b406a525db7fbd12beb7e589708cd6",
}
COMPCHECK = {
    "url": "https://raw.githubusercontent.com/compsuite-team/CompCheck/"
           "937d1d1495c4ff5449443183b70f465d1fe0b4d0/knowledge/knowledge.json",
    "sha256": "81b2f6d2327df2cbac7c59de66842f682892b74bc0f4f9e7f12e74dc33674240",
}


def pinned_rows(path, source):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError("input does not match the pinned registry digest")
    return json.loads(data)


def overlap(suite_rows, knowledge_rows):
    keys = {
        (row["client"], row["lib"], old, row["new_version"], row["test"])
        for row in knowledge_rows
        for old in row["versions"]
    }
    return sum(
        (row["client"], row["lib"], row["old"], row["new"], row["test"]) in keys
        for row in suite_rows
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compsuite", type=Path)
    parser.add_argument("compcheck", type=Path)
    args = parser.parse_args()
    try:
        suite = pinned_rows(args.compsuite, COMPSUITE)
        knowledge = pinned_rows(args.compcheck, COMPCHECK)
    except (OSError, ValueError):
        parser.exit(1, "Could not read both pinned registry files.\n")
    print(json.dumps({
        "compsuite": {**COMPSUITE, "entries": len(suite)},
        "compcheck": {**COMPCHECK, "entries": len(knowledge)},
        "matching_compsuite_entries": overlap(suite, knowledge),
    }, indent=2))


if __name__ == "__main__":
    main()
