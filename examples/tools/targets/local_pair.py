"""Import two source directories into a named local Git repository for a target sidecar."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}")


def import_pair(before, after, store, name):
    if not NAME.fullmatch(name):
        raise ValueError("a local source name needs 1–80 letters, digits, underscores or hyphens")
    before, after, store = (Path(p).resolve() for p in (before, after, store))
    if not before.is_dir() or not after.is_dir() or any(store.is_relative_to(p) for p in (before, after)):
        raise ValueError("supply two existing source directories and a store outside both")
    store.mkdir(parents=True, exist_ok=True)
    target = store / name
    env = {"PATH": os.environ["PATH"], "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "Local source pair", "GIT_COMMITTER_NAME": "Local source pair",
           "GIT_AUTHOR_EMAIL": "pair@localhost", "GIT_COMMITTER_EMAIL": "pair@localhost",
           "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
    with tempfile.TemporaryDirectory(dir=store) as tmp:
        repo = Path(tmp) / "repository"
        subprocess.run(["git", "init", "-q", "--bare", "--object-format=sha1", str(repo)], env=env, check=True)

        def git(*args, data=None):
            return subprocess.check_output(["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                                           input=data, env=env).strip()

        revisions = {}
        parent = None
        for side, tree in (("old", before), ("new", after)):
            # Hash literal bytes without clean filters or newline conversion, including executable mode.
            index = bytearray()
            for directory, directories, files in os.walk(tree):
                directories[:] = sorted(d for d in directories if d != ".git")
                if any((Path(directory) / d).is_symlink() for d in directories):
                    raise ValueError("plain source import requires ordinary directories")
                for leaf in sorted(f for f in files if f != ".git"):
                    path = Path(directory) / leaf
                    mode = path.lstat().st_mode
                    if not stat.S_ISREG(mode):
                        raise ValueError(f"plain source import requires regular files: {path.relative_to(tree)}")
                    blob = git("hash-object", "-w", "--stdin", "--no-filters", data=path.read_bytes())
                    index.extend((b"100755" if mode & stat.S_IXUSR else b"100644") + b" " + blob +
                                 b"\t" + os.fsencode(path.relative_to(tree)) + b"\0")
            if not index:
                raise ValueError(f"the {side} directory contains no source files")
            env["GIT_INDEX_FILE"] = str(Path(tmp) / f"index-{side}")
            git("update-index", "-z", "--index-info", data=index)
            tree_id = git("write-tree").decode()
            parents = ["-p", parent] if parent else []
            commit = git("commit-tree", tree_id, *parents, "-m", f"Local {side} source tree").decode()
            git("update-ref", f"refs/heads/{side}", commit)
            revisions[side] = {"commit": commit, "checked": f"Imported local source bytes, Git tree {tree_id}.",
                               **({"parent": parent} if parent else {})}
            parent = commit
        git("symbolic-ref", "HEAD", "refs/heads/new")
        with (store / ".publish.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if target.exists() or target.is_symlink():
                raise ValueError(f"local repository {name} already exists; choose a new name")
            repo.rename(target)
    return {"repository": "local-git:" + name, "revisions": revisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("before", "after", "store", "name"):
        parser.add_argument(arg)
    args = parser.parse_args()
    try:
        print(json.dumps(import_pair(args.before, args.after, args.store, args.name), indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
