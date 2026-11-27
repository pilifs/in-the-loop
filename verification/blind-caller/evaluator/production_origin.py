"""Disambiguate a production type whose name resembles a test, on the unchanged physical artifacts."""
import hashlib
from pathlib import PurePosixPath
import re
import sys
import zipfile

from eligibility_inventory import BATCHES, CACHE, ROOT, digest, example, read, worktree
from packet_view import CODE_OR_COMMENT, PreparationStop, raw_git, source_names, upstream_test_classes


def plain_source(path, binary, source):
    logical = binary + ".java"
    if not any(("/"+path).endswith(marker + logical) for marker in ("/src/main/java/", "/src/java/")):
        return False
    prefix = path.rsplit("/src/", 1)[0].lower().split("/") if "/src/" in path else []
    if any(p in {"test", "tests", "testdata", "fixture", "fixtures", "examples", "samples", "demos"}
           or p.endswith(("-test", "-tests", "-fixtures")) for p in prefix):
        return False
    package, _, name = binary.rpartition("/")
    # Only declarations and executable code establish source ownership. Examples
    # in comments and strings are still removed from the fresh producer source view.
    text = CODE_OR_COMMENT.sub(lambda m: " " * len(m[0]), source.decode("utf-8", "replace"))
    return (bool(re.search(r"\bpackage\s+" + re.escape(package.replace("/", ".")) + r"\s*;", text))
            and bool(re.search(r"\b(?:class|interface|enum|record)\s+" + re.escape(name) + r"\b", text))
            and not re.search(r"@(?:[\w.]+\.)?(?:Test|ParameterizedTest|Factory|TestFactory)\b|\bextends\s+(?:junit\.framework\.)?TestCase\b", text))


def inspect(row):
    from functional_scope import identity
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets import runtime_jar
    cache = CACHE / BATCHES[row["batch"]][3]
    tree = worktree(cache, row["slot"], "fix")
    suspected = upstream_test_classes(tree, row["pins"])
    runtime = read(example(row["number"]) / "runtime.json")
    rows = []
    exempt = set()
    for side, revision in row["pins"].items():
        paths = source_names(tree, revision)
        cpaths = {name for dep in runtime["deployments"].values() for name in dep["classpath"][side]}
        for cp in sorted(cpaths):
            jar = (cache / cp).resolve(strict=True)
            if not jar.is_relative_to(cache.resolve()) or digest(jar) != runtime["sha256"][cp]:
                raise PreparationStop("original artifact digest differs in the production-source review")
            with zipfile.ZipFile(jar) as archive:
                for physical in archive.namelist():
                    if not physical.endswith(".class"):
                        continue
                    logical = re.sub(r"^META-INF/versions/\d+/", "", physical.removesuffix(".class"))
                    owner = logical.split("$")[0]
                    if owner not in suspected:
                        continue
                    choices = [p for p in paths if p.endswith("/"+owner+".java") or p == owner+".java"]
                    if len(choices) != 1:
                        raise PreparationStop("ambiguous or absent source ownership for a test-like original binary")
                    path, = choices
                    source = raw_git(tree, "show", f"{revision}:{path}")
                    data = archive.read(physical)
                    if (not plain_source(path, owner, source) or runtime_jar.this_class(data) != logical
                            or runtime_jar.source_file(data) != PurePosixPath(path).name):
                        raise PreparationStop("the original binary lacks a verified, unique production-only source")
                    rows.append({"side": side, "revision": revision, "source": path, "sourceSha256": hashlib.sha256(source).hexdigest(),
                                 "class": logical, "sourceFile": runtime_jar.source_file(data), "physicalEntry": physical,
                                 "classSha256": hashlib.sha256(data).hexdigest(), "artifactSha256": runtime["sha256"][cp]})
                    exempt.add(owner)
    if not rows:
        raise PreparationStop("there is no original production-only binary to disambiguate")
    for owner in exempt:
        if {r["side"] for r in rows if r["class"].split("$")[0] == owner} != {"parent", "fix"}:
            raise PreparationStop("the production-only origin was not verified on both pins")
    return {"schema": "post-reveal-production-origin/v1", "identitySha256": identity(row),
            "classNames": sorted(exempt), "evidence": rows, "jarBytesChanged": False}
