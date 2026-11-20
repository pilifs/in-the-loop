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


def products(record, recipe):
    """Check the build recipe and clean checkout before using a captured classpath."""
    if record.get("schema") != "upstream-jar-build/v1" or runtime_upstream.check_recipe(
            recipe["commit"], record["recipe"]) != recipe:
        raise runtime_maven.Blocked("lock", "the captured upstream build belongs to a different recipe")
    build = record["build"]
    checkout = build["checkout"]
    if (checkout.get("commit") != recipe["commit"] or checkout.get("fetchedFrom") != recipe["repository"]
            or checkout.get("changedByBuild") != [] or checkout.get("patched")
            or (recipe["parent"] and checkout.get("parents", [])[:1] != [recipe["parent"]])):
        raise runtime_maven.Blocked("lock", "the captured checkout does not identify the selected clean revision")
    entries = [(a["path"], a["sha256"], a["role"], a["coordinates"], a["origin"]) for a in record["artifacts"]]
    outputs = build["outputs"]
    original = [jar for jar in outputs["jars"] if jar["path"] == outputs["original"] and not jar["auxiliary"]]
    if (len(original) != 1 or not entries or entries[0][1] != original[0]["sha256"]
            or entries[0][0] != "built/" + Path(outputs["original"]).name
            or len({e[0] for e in entries}) != len(entries)):
        raise runtime_maven.Blocked("lock", "the captured JAR does not match the recorded Maven output")
    for i, (name, digest, role, _, _) in enumerate(entries):
        if (role != ("dependency" if i else "original") or Path(name).parts[:1] != (("lib",) if i else ("built",))
                or ".." in Path(name).parts or not runtime_maven.SHA256.fullmatch(digest)):
            raise runtime_maven.Blocked("lock", "invalid path, role or digest in the captured classpath")
    return entries


def restore(entries, workdir):
    cache = runtime_maven.Cache()
    if not all(cache.path(digest).is_file() for _, digest, _, _, _ in entries):
        return False
    for name, digest, _, _, _ in entries:
        path = workdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cache.restore(digest, path)[0]:
            return False
    return True


def acquire(entry, destination, network):
    """Materialize one dependency by the declared build or published release, checking any pinned output digest."""
    cache = runtime_maven.Cache()
    if "build" not in entry:
        item = runtime_maven.check_item(entry, "dependency")
        runtime_maven.acquire(item, destination, cache, network=network)
        return f"published {item['coordinates']} at {item['sha256']}"
    recipe = runtime_upstream.check_recipe(entry["commit"], entry)
    origin = f"full {recipe['tool']} build of {recipe['repository']} at {recipe['commit']}"
    digest = entry.get("sha256")
    if digest and not runtime_maven.SHA256.fullmatch(digest):
        raise runtime_maven.Blocked("lock", "invalid upstream JAR digest")
    if digest and cache.restore(digest, destination)[0]:
        return origin
    if not network:
        raise runtime_maven.Blocked("acquire", f"{origin} needs acquisition")
    record = destination.with_suffix(".build.json")
    products = capture(entry, record)
    original, = [item for item in products if item["role"] == "original"]
    if digest and original["sha256"] != digest:
        raise runtime_maven.Blocked("build", f"{origin} produced {original['sha256']}, expected {digest}")
    if not cache.restore(original["sha256"], destination)[0]:
        raise runtime_maven.Blocked("acquire", f"could not restore the verified {origin}")
    return origin


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
