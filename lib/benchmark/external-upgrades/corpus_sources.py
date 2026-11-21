"""Fetch the corpus's pinned original Git objects, once per client, into an external local cache."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    args = ap.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    clients = defaultdict(list)
    for case in json.loads((HERE / "corpus.json").read_text())["cases"]:
        clients[case["repository"]].append(case)
    mapping = {}
    for url, cases in clients.items():
        owner, name = url.removeprefix("https://github.com/").split("/")
        repo = root / owner / (name + ".git")
        repo.parent.mkdir(exist_ok=True)
        if not repo.exists():
            subprocess.run(["git", "init", "--bare", "-q", str(repo)], check=True)
        git = ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null"]
        refs = {}
        for case in cases:
            mapping[case["id"]] = str(repo)
            for side, sha in case["revisions"].items():
                if subprocess.run([*git, "cat-file", "-e", sha + "^{commit}"], capture_output=True).returncode:
                    ref = ("refs/tags/" + case["dependency"].replace(":", "--") + "-" + case["versions"][side]
                           if case["origin"].startswith("CompSuite") else sha)
                    refs[ref] = "refs/corpus/" + sha
        if refs:
            subprocess.run([*git, "fetch", "--no-tags", "--depth=2", url,
                            *(f"{ref}:{local}" for ref, local in refs.items())], check=True)
            time.sleep(1)
        for case in cases:
            for sha in case["revisions"].values():
                subprocess.run([*git, "cat-file", "-e", sha + "^{commit}"], check=True)
    (root / "repos.json").write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"{len(mapping)} upgrade pairs in {len(clients)} original repositories")


if __name__ == "__main__":
    main()
