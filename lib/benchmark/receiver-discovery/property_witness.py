"""Seek refutations of an ordinary finite public claim in legal property prestates; replay its unchanged entry."""

import argparse
import os
from pathlib import Path
import tempfile

from callers import JDK, RESULTS, ROOT, read, sha
from investigate import command, compiler, inventory, native, original, write
from process_states import prepare, setup_line

HERE = Path(__file__).resolve().parent


def original_call(tools, cp, entry, arg, setting=None):
    owner = entry["owner"].replace("/", ".")
    params = [owner, owner, entry["method"], entry["descriptor"], str(arg)]
    cmd = [JDK / "bin/java", "-ea", "-Xverify:all", "-cp", os.pathsep.join(map(str, [tools, *cp]))]
    if setting is None:
        cmd += ["org.intheloop.observation.CallOnce"]
    else:
        key, value = setting
        cmd += ["InitialProperty", "absent" if value is None else "value", key, value or ""]
    lines = command([*cmd, *params], timeout=30).splitlines()
    if lines[0] != "class " + entry["binding"]["sha256"]:
        raise ValueError("original class binding differs")
    return lines


def qualify(checker, cp, tools, tmp, entry, key, expected, first, count, limits, downstream):
    """This route can return only a violating original input or an open claim."""
    owner = entry["owner"].replace("/", ".")
    method = entry["method"]
    if (entry["descriptor"], expected) not in (("(I)Z", "true"), ("(I)I", "1")):
        raise ValueError("unsupported ordinary predicate")
    dest = tmp / "slices"
    dest.mkdir()
    source = tmp / "PropertyWitnessSlice.java"
    # The candidates are independent of the library's accepted spelling and the expected counterexample.
    states = [("missing", None), ("other", "_"), ("newline", "\n")]
    body = ["public final class PropertyWitnessSlice {"]
    for name, value in states:
        body.append(
            f"public static boolean {name}(int selector) {{ {setup_line(key,value)} return {owner}.{method}(selector)=={expected}; }}"
        )
    source.write_text("\n".join(body) + "\n}\n")
    command(
        [
            JDK / "bin/javac",
            "-g",
            "-parameters",
            "-proc:none",
            "-cp",
            os.pathsep.join(map(str, cp)),
            "-d",
            dest,
            source,
        ]
    )
    result = {
        "entry": f"{owner}#{method}{entry['descriptor']}",
        "originalClassSha256": entry["binding"]["sha256"],
        "assert": "result" if expected == "true" else "result == 1",
        "admittedSelectors": list(range(first, count)),
        "unwind": limits[0],
        "maxArrayLength": limits[1],
        "property": key,
        "attempts": {},
        "disposition": "unresolved",
    }
    expected_line = "returned " + expected
    for label, value in states:
        attempt = native(
            checker,
            [dest, *cp],
            "PropertyWitnessSlice#" + label,
            f"selector >= {first} && selector < {count}",
            *limits,
            60,
            tmp / ("trial-" + label),
        )
        row = {"value": value, "native": attempt}
        result["attempts"][label] = row
        if attempt["verdict"] != "violation":
            continue
        (arg,) = attempt["counterexample"]["inputs"]
        if arg["type"] != "int" or not first <= arg["value"] < count:
            raise ValueError("witness outside the registered inputs")
        raw = original_call(tools, cp, entry, arg["value"], (key, value))
        row["originalJvm"] = raw
        if raw[-1] not in ("returned false", "returned 0") or raw[-1] == expected_line:
            # An escaped exception, including failed class initialization, does not disprove a return predicate here.
            continue
        default = original_call(tools, cp, entry, arg["value"])
        row["freshDefaultJvm"] = default
        row["input"] = arg["value"]
        row["sliceClassSha256"] = sha(dest / "PropertyWitnessSlice.class")
        if downstream:
            lines = original(
                tools,
                [dest, *cp],
                downstream,
                {"pc": 0, "kind": "call"},
                inventory(checker, [dest, *cp], "PropertyWitnessSlice#" + label),
                [str(arg["value"])],
            )
            row["libraryEntryJvm"] = lines
            row["libraryMethodReached"] = any(v.startswith("hit ") for v in lines)
        result.update(
            disposition="refuted", witnessPrestate=label, reproducesOnFreshDefault=default[-1] == raw[-1]
        )
        break
    return result


def measure(family, dest=None):
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    result = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checkerSha256": sha(checker),
        "sides": {},
    }
    frozen = read(RESULTS / "scope.json")
    for side in (("old", "new") if family == "xz" else ("parent", "fix")):
        with tempfile.TemporaryDirectory() as work:
            tmp = Path(work)
            cp, _, _ = prepare(family, side, tmp, read(RESULTS / "scope.json"))
            tools = compiler(tmp)
            command([JDK / "bin/javac", "-cp", tools, "-d", tools, HERE / "history/InitialProperty.java"])
            if family == "xz":
                key = "org.tukaani.xz.ArrayCache"
                entries = {"frame": ("UpgradeCallerClaim#matches", "true", 0, 4)}
                limits = (64, 128)
                original_check = read(
                    ROOT
                    / "verification/domain-foundations/receiver-verified/04/callers/commons-compress-767.json"
                )
                if (
                    sha(cp[0] / "UpgradeCallerClaim.class")
                    != original_check["nativeCaller"]["adapterClassSha256"]
                ):
                    raise ValueError("different ordinary XZ claim bytes")
                downstream = inventory(
                    checker, cp, "org.apache.commons.compress.compressors.xz.XZCompressorInputStream#read()"
                )
            else:
                key = "line.separator"
                entries = {
                    name: (
                        "organic.TreeOrder#" + ("postorder" if name == "nonempty" else name),
                        "1",
                        int(name == "nonempty"),
                        2,
                    )
                    for name in ("postorder", "preorder", "terminal", "nonempty")
                }
                limits = (96, 64)
                downstream = None
            receipts = {}
            for label, (target, expected, first, count) in entries.items():
                t = tmp / label
                t.mkdir()
                bound = inventory(checker, cp, target)
                if family == "javaparser":
                    pin = frozen["tasks"]["360"][label + "-" + side]
                    if (
                        pin["entry"] != target + bound["descriptor"]
                        or pin["assert"] != "result == 1"
                        or pin["assume"] != f"code >= {first} && code < {count}"
                        or pin["bounds"] != {"unwind": limits[0], "maxArrayLength": limits[1]}
                        or pin["environment"] != "ordinary"
                    ):
                        raise ValueError("different registered JavaParser statement")
                receipts[label] = qualify(
                    checker,
                    cp,
                    tools,
                    t,
                    inventory(checker, cp, target),
                    key,
                    expected,
                    first,
                    count,
                    limits,
                    downstream,
                )
            result["sides"][side] = receipts
    dest = dest or RESULTS / "transfer" / (family + "-ordinary-witnesses")
    dest.mkdir(parents=True, exist_ok=True)
    write(dest / "measurement.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=["xz", "javaparser"])
    parser.add_argument("--output", type=Path, help="write this repeat to a separate receipt directory")
    args = parser.parse_args()
    measure(args.family, args.output)
