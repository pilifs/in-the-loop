"""Capture the selected JAR of a full upstream Maven build and its resolved classpath.

The JSON record is portable. The bytes are stored in the same content-addressed
cache as published dependencies and can be recovered by repeating the recipe.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in ("", None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import runtime_maven, runtime_upstream


def capture(entry, destination):
    recipe = runtime_upstream.check_recipe(entry["commit"], entry)
    cache = runtime_maven.Cache()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    provenance, logs = {}, []
    with tempfile.TemporaryDirectory(prefix="upstream-jar-") as directory:
        work = Path(directory)
        try:
            files = runtime_upstream.build(recipe, work, entry["class"].replace(".", "/"),
                                           logs, provenance, cache=cache)
            if recipe["parent"] and provenance["checkout"]["parents"][0] != recipe["parent"]:
                raise ValueError("the build's first parent differs from the recorded repair boundary")
            artifacts = []
            for path, digest, role, coordinates, origin in files:
                cache.store(work / path, digest)
                artifacts.append({"role": role, "sha256": digest, "path": path,
                                  "coordinates": coordinates, "origin": origin})
            result = {"schema": "upstream-jar-build/v1", "recipe": entry,
                      "artifacts": artifacts, "build": provenance}
            resolution = destination.with_suffix(".resolution.json")
            shutil.copyfile(work / "maven/resolution.json", resolution)
            result["resolutionFile"] = resolution.name
        except runtime_maven.Blocked as error:
            print(f"{entry['commit']}: {error}", file=sys.stderr)
            # The pipeline archives stdout and stderr even when preparation fails.
            for log in logs[-2:]:
                print("\n".join((work / log).read_text().splitlines()[-16:]), file=sys.stderr)
            raise
    destination.write_text(json.dumps(result, indent=2) + "\n")
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipes", type=Path)
    parser.add_argument("name")
    parser.add_argument("record", type=Path)
    args = parser.parse_args()
    entry = json.loads(args.recipes.read_text())[args.name]
    for artifact in capture(entry, args.record):
        print(artifact["role"], artifact["sha256"], artifact["path"])


if __name__ == "__main__":
    main()
