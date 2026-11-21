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
        required = {}
        depth = max(case.get("gitHistoryDepth", 2) for case in cases)
        for case in cases:
            mapping[case["id"]] = str(repo)
            for side, sha in case["revisions"].items():
                if case["origin"].startswith("CompSuite"):
                    ref = "refs/tags/" + case["dependency"].replace(":", "--") + "-" + case["versions"][side]
                    local = ref
                else:
                    ref, local = sha, "refs/corpus/" + sha
                required[local] = sha
                obj = subprocess.run([*git, "rev-parse", "--verify", local + "^{commit}"], capture_output=True, text=True)
                if obj.returncode or obj.stdout.strip() != sha:
                    refs[ref] = local
        if refs:
            subprocess.run([*git, "fetch", "--no-tags", f"--depth={depth}", url,
                            *(f"{ref}:{local}" for ref, local in refs.items())], check=True)
            time.sleep(1)
        for ref, sha in required.items():
            resolved = subprocess.check_output([*git, "rev-parse", "--verify", ref + "^{commit}"], text=True).strip()
            if resolved != sha:
                raise ValueError(f"{ref} resolves to {resolved}, expected {sha}")
    (root / "repos.json").write_text(json.dumps(mapping, indent=2) + "\n")
    print(f"{len(mapping)} upgrade pairs in {len(clients)} original repositories")


if __name__ == "__main__":
    main()
