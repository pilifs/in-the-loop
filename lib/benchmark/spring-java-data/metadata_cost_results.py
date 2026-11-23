"""Audit both complete timing routes and the raw selectors the archive holds for each trial."""
import math
from pathlib import Path
import tarfile
import tempfile

import metadata_cost as cost
from measure import ROOT, read, digest as sha
from startup_results import metadata_cases, rel, require


class ArchiveView:
    """Read only the eighty named measurements, wrappers, JVM tables and raw outcomes."""
    def __init__(self, job, archive, scratch):
        self.record = job.record
        self.scratch = scratch
        self.archive = archive
        expected = {p for i, order in enumerate(cost.ORDERS, 1) for mode in order for side in cost.SIDES
                    for p in cost.outputs(Path(f"pair-{i}") / mode, side)}
        self.members = {Path(m.name): m for m in archive.getmembers()}
        require(set(self.members) == expected and len(archive.getmembers()) == len(expected)
                and all(m.isfile() for m in self.members.values()), "different paired trial files")

    def output(self, path):
        member = self.members[path]
        dest = self.scratch / path
        if not dest.is_file():
            dest.parent.mkdir(exist_ok=True, parents=True)
            dest.write_bytes(self.archive.extractfile(member).read())
        return dest


def comparison(job, case, controls):
    base = cost.DEST.relative_to(ROOT)
    record = job.output(base / "measurement.json")
    data = read(record)
    archive = job.output(base / "cases.tar.gz")
    trials = [f"pair-{i}/{mode}" for i, order in enumerate(cost.ORDERS, 1) for mode in order]
    require(data["job"] == job.record["id"] and data["source"] == job.record["sourceCommit"]
            and data["libTree"] == job.record["jvmcontract"]["libTree"] and job.record["status"] == "passed"
            and data["casesSha256"] == sha(archive) and list(data["trials"]) == trials, "different timing trials or order")
    graphs = read(ROOT / "verification/spring-java-data/exact-classpaths/classes.json")["372"]
    totals = {}
    with tarfile.open(archive) as files, tempfile.TemporaryDirectory(prefix="property-trial-audit-") as tmp:
        scratch = Path(tmp)
        view = ArchiveView(job, files, scratch)
        for label, sides in data["trials"].items():
            root = Path(label)
            ordinary = root.name == "ordinary"
            results = metadata_cases(view, case, graphs, data["checkerSha256"], ordinary_startup=ordinary,
                                     destination=root, locator=lambda p: p.relative_to(scratch).as_posix())
            require(set(sides) == set(cost.SIDES), "missing historical timing side")
            whole = 0
            checker = 0
            for side, times in sides.items():
                trial = read(view.output(root / side / "measurement.json"))
                calls = cost.qualified_calls(trial, side, root.name)
                reference = controls["ordinaryMetadata"][side]
                require(reference["lookupProviderSha256"] == results[side]["lookupProviderSha256"]
                        and all([(r["selector"], r["jvmResult"], r["verdict"]) for r in reference["tasks"][method]]
                                == [(r["selector"], r["jvmResult"], r["verdict"]) for r in results[side]["tasks"][method]]
                                for method in ("components", "getters")), "different historical observations across timing routes")
                measured = round(sum(c["seconds"] for c in calls), 6)
                require(measured == times["checkerSeconds"] and math.isfinite(times["wholeSeconds"])
                        and 0 < measured <= times["wholeSeconds"], "incomplete elapsed time or different checker time")
                whole += times["wholeSeconds"]
                checker += measured
            totals[label] = {"wholeSeconds": round(whole, 6), "checkerSeconds": round(checker, 6), "sides": sides}
    return {"measurement": rel(record), "rawCases": rel(archive), "checkerSha256": data["checkerSha256"],
            "selectors": 48, "trials": totals}
