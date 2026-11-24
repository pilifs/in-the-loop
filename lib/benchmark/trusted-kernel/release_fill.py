"""Qualify the fastutil range theorem on its release JAR and the earlier JDK-only checker."""

import argparse
import json
import os
from pathlib import Path
import tempfile
import zipfile

import fastutil_certificate
from frozen_range import long_kernel
from prepare import digest, request
from range_qualification import DIRECT, extract_arrays
from range_transfer import RELEASES, bound_case, check, extract, probe, regression, release
from replay import build_kernel


def qualify(tmp):
    frozen = long_kernel(tmp / "post-jdk")
    compiled = tmp / "new"
    compiled.mkdir()
    binary, build = build_kernel(compiled)
    name = "fastutil-8.5.15"
    jar = release(name)
    sha, prefix = RELEASES[name]
    owner, external = prefix + "ints/IntArrays", prefix + "Arrays"
    with zipfile.ZipFile(jar) as package:
        artifact = extract(package, owner, tmp)
        guard = extract(package, external, tmp)
    claim = request(DIRECT, owner, digest(artifact.read_bytes()), "fill ([IIII)V", "ensureFromTo ([III)V")
    claim += f"callee {external} {digest(guard.read_bytes())}\n"
    args, row = bound_case(tmp, claim, artifact, lambda r, a: fastutil_certificate.issue(r, a, guard), [guard])
    req, cert, _, _ = args
    # The old request vocabulary admits an external callee for a caller observation only.
    before = check(frozen, *args, 2, "bad support")
    after = check(binary, *args, 0, "obligations 70")
    keys = cert.read_text().splitlines()
    controls = []
    for kind in ("extend-written-suffix", "exhausted-cursor-minus-one", "extend-written-prefix"):
        missing, = [key for key in keys if key.endswith(" " + kind)]
        partial = tmp / (kind + ".cert")
        partial.write_text("\n".join(key for key in keys if key != missing) + "\n")
        controls.append({"missing": missing, "result": check(binary, req, partial, artifact, [guard], 2,
                                                              "missing obligation " + missing)})
    grids = {}
    for mode in ("-ea", "-da"):
        grid = probe(tmp, "FastutilFill", classpath=[jar], options=[mode])
        if grid["observations"][:3] != [
            "checks=7745 pass=7745 zeroOriginBranch=2735 otherBranch=5010",
            "[0,2) value 99 on [0,0,0] -> [99, 99, 0]",
            "[1,1) value 99 on [5,6,7] -> [5, 6, 7]",
        ]:
            raise ValueError(grid)
        grids[mode] = grid
    arrays = extract_arrays(tmp / "jdk-arrays.bin")
    return {"schema": "release-range-qualification/v1", "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
            "key": f"{name}/IntArrays.fill", "jarSha256": sha, **row, "build": build, "before": before,
            "after": after, "controls": controls, "jvm": grids, "regressions": regression(binary, arrays, tmp)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    with tempfile.TemporaryDirectory() as directory:
        data = qualify(Path(directory))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n")
    print(data["key"], data["after"]["stdout"])
