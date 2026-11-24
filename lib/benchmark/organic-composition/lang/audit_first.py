"""Check the public and private dispositions of the first frozen week-date transfer."""
import json
import zipfile
from pathlib import Path

from register import CASE, PARSER, sha
from audit import recheck
from freeze import verify
from plan_run import OUTPUT, ROOT
import sys
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_helpers, runtime_jar


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    verify()
    recheck("lang", "first")
    spec = json.loads((CASE / "helper.json").read_bytes())
    registration = json.loads((CASE / "registration.json").read_bytes())
    require(all(sha(CASE / k) == v for k, v in registration["inputs"].items()), "registration changed")
    require(registration["productCommitment"] == sha(CASE.parent / "freeze.json"), "shared commitment changed")
    target = ROOT / OUTPUT / "lang"
    sides = {}
    for side in ("old", "new"):
        manifest = json.loads((CASE / side / "prepared.json").read_bytes())
        artifact, = manifest["classpath"]
        jar = Path(artifact["file"])
        require(sha(jar) == artifact["sha256"], "different original JAR")
        data = runtime_jar.read_class(jar, PARSER.replace(".", "/"))
        method = runtime_jar.method_flags(data, "toCalendarDayOfWeek", "(I)I")
        require(method is None if side == "old" else method == 10, "original private/absent binding differs")
        try:
            change_helpers.declaration(spec, data)
        except ValueError as error:
            require(str(error) == "expected original public static bytecode without a synchronized frame", str(error))
            sides[side] = {"commit": manifest["commit"], "jar": artifact["sha256"], "flags": method,
                           "availability": "absent" if side == "old" else "private static", "frozenRefusal": str(error)}
        else:
            raise ValueError("frozen checker admitted an absent or private declaration")
    summaries = {}
    with zipfile.ZipFile(target / "first/plans.zip") as archive:
        for mode in ("cold", "warm", "clean", "unrelated-warm", "unrelated-clean", "wrong-warm", "wrong-clean"):
            rows = json.loads(archive.read(mode + ".json"))["claims"]
            require(len(rows) == 4, "missing registered or helper-control workflow")
            summaries[mode] = {}
            for node in rows:
                status = node["status"]
                private = node["id"].endswith("-private")
                require(status == ("open" if private else "established"), "unexpected public or private disposition")
                info = {"status": status, "firstOpenDependency": node.get("firstOpenDependency")}
                if not private:
                    require(len(node["children"]) == 4 and all(r["status"] == "established" for r in node["children"]),
                            "missing original locale/mode partition")
                    proof = json.loads(archive.read(node["receipt"]["path"]))
                    for side in sides:
                        require(all(t["qualifiedMethodEntries"] == 2 and t["observations"] == [n[side]] * 2
                                    for t, n in zip(proof["sides"][side]["trials"], node["children"], strict=True)),
                                "missing original calendar observations")
                    info["sides"] = {s: v["action"] for s, v in node["execution"].items()}
                summaries[mode][node["id"]] = info
    require(all(value == "exact reuse" for value in summaries["warm"]["preserved"]["sides"].values()),
            "the positive calendar sides missed exact reuse")
    report = {"privateDeclaration": spec["entry"], "originalBindings": sides, "runs": summaries,
              "scope": "Two finite registered ordinary workflows; the private-helper controls are separately open on the frozen interface."}
    (target / "frozen-dispositions.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Both public workflows established; original parent lacks the private declaration, and the fixed declaration is private.")


if __name__ == "__main__":
    main()
