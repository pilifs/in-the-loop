"""Prepare ordinary review-time operator inputs for one of the two disclosed opening calibrations."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = {"348": "u-7b26f3c1", "349": "u-d8e01af4"}
PRIMARY = "testReturnGeneratedKeysForMultipleInsertedValuesInOneStatement"
COMPANION = "testReturnGeneratedKeysForMultipleCallsOfInsert"
COMMENT = "h2 only returns the last generated key"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def method_span(data, name):
    method = re.search(rb"(?m)^    public void " + re.escape(name.encode()) + rb"\s*\(", data)
    if method is None:
        raise ValueError("method absent: " + name)
    start = data.rfind(b"    @Test", 0, method.start())
    end = re.search(rb"(?m)^    }\r?\n", data[method.end():])
    if start < 0 or method.start() - start >= 140 or end is None:
        raise ValueError("method no longer matches its reviewed source span")
    return start, method.end() + end.end()


def disposition(number, name, data):
    role = ("dependency_descriptor" if Path(name).name == "pom.xml" else
            "production" if name.startswith("src/main/") else "review_time_file")
    result = {"role": role, "action": "copy", "original_sha256": sha(data)}
    spans = []
    if number == "348" and name.endswith("/DatabaseTestBase.java"):
        spans = [method_span(data, method) for method in (PRIMARY, COMPANION)]
        for comment in re.finditer(rb"(?m)^\s*// " + COMMENT.encode() + rb"\r?\n", data):
            if not any(start <= comment.start() < end for start, end in spans):
                spans.append(comment.span())
    if number == "348" and name.endswith("/DatabaseDerbyTest.java"):
        spans = [method_span(data, "testReturnGeneratedKeys")]
    if spans:
        pieces = sorted(spans)
        retained = data
        for start, end in reversed(pieces):
            retained = retained[:start] + retained[end:]
        result.update(action="strip", reason="Withhold the named discriminator, companion or a direct duplicate "
                      "while keeping unrelated review-time tests.",
                      deletions=[{"start": a, "end": b, "sha256": sha(data[a:b])} for a, b in pieces],
                      retained_sha256=sha(retained))
    return result


def review_tree(number, repo, revision):
    listing = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "--full-tree", "-rz", revision])
    result = {}
    with subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as reader:
        for entry in listing.rstrip(b"\0").split(b"\0"):
            header, name = entry.split(b"\t", 1)
            _, kind, oid = header.split()
            if kind != b"blob":
                raise ValueError("unexpected non-file in the disclosed pair")
            reader.stdin.write(oid + b"\n")
            reader.stdin.flush()
            oid_read, object_kind, length = reader.stdout.readline().split()
            data = reader.stdout.read(int(length))
            if oid_read != oid or object_kind != b"blob" or reader.stdout.read(1) != b"\n":
                raise ValueError("incomplete Git object")
            result[name.decode()] = disposition(number, name.decode(), data)
        reader.stdin.close()
    if reader.returncode:
        raise ValueError("Git object reader failed")
    return result


def archive(path, expected, role):
    body = path.read_bytes()
    if sha(body) != expected:
        raise ValueError(f"{path.name} differs from the original independently replayed JAR")
    item = {"role": role, "source": str(path.resolve()), "sha256": expected}
    if role == "client":
        with zipfile.ZipFile(path) as jar:
            item["production_members"] = {name.filename: sha(jar.read(name)) for name in jar.infolist() if not name.is_dir()}
    return item


def runtime(number, folder, target, side, jars, text_run):
    if number == "348":
        items = [a for a in target["preparation"]["artifacts"] if a["revision"] == side]
        source = json.loads((folder / "records/jvm-receipt.json").read_text())["sides"][side]
        if [a["coordinates"] for a in items[1:]] != source["classpathOrder"]["observation"]:
            raise ValueError("ordered original H2 observation classpath changed")
        paths = [(jars / a["url"].rsplit("/", 1)[-1], a["sha256"]) for a in items]
    else:
        evidence = json.loads((folder / "records/full-source-jvm.json").read_text())["sides"][side]["classpath"]
        client, lang = evidence[1:]
        paths = [(text_run / side / client["name"], client["sha256"]), (jars / lang["name"], lang["sha256"])]
    return [archive(path, digest, "client" if i == 0 else "dependency") for i, (path, digest) in enumerate(paths)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("example", choices=CASES)
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--jars", required=True, type=Path)
    p.add_argument("--text-run", type=Path, help="349 full-source JVM reproduction with old/client.jar and new/client.jar")
    p.add_argument("--out", type=Path, required=True, help="fresh private directory outside the product checkout")
    a = p.parse_args()
    if a.example == "349" and not a.text_run:
        p.error("349 requires --text-run")
    out = a.out.resolve()
    if out.is_relative_to(ROOT):
        p.error("the curator plan belongs outside the checkout")
    out.mkdir(parents=True, exist_ok=False)
    folder = next((ROOT / "examples").glob(a.example + "-*/target.json")).parent
    target = json.loads((folder / "target.json").read_text())
    forbidden = ([PRIMARY, COMPANION, COMMENT, "compsuite-team"] if a.example == "348"
                 else ["omit-quote-doubling.patch", "external-upgrade-open-review/v1", "disclosed opening calibration"])
    plan = {"case_id": CASES[a.example], "forbidden_literals": forbidden}
    for side in ("old", "new"):
        revision = target["history"]["revisions"][side]["commit"]
        plan[side] = {"repository": str(a.repo.resolve()), "revision": revision,
                      "files": review_tree(a.example, a.repo, revision),
                      "runtime_artifacts": runtime(a.example, folder, target, side, a.jars, a.text_run)}
    private = out / "curator.json"
    private.write_text(json.dumps(plan, indent=2) + "\n")
    subprocess.run([sys.executable, HERE / "curation/export_pair.py", private, out / "release"], check=True)
    for file in ("pair/pair.json", "dependencies/manifest.json"):
        print(sha((out / "release" / file).read_bytes()), file)


if __name__ == "__main__":
    main()
