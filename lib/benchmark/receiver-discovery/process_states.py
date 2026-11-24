"""Bind one property prestate, start a new JVM, and compare the selected public call and class state."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from callers import EXTERNAL, JDK, ROOT, RESULTS, read, sha, upgrade
from configuration import paths
from investigate import command, compiler, inventory, native, original, write

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import route, runtime
from targets.upgrade_receiver import caller_source, java_string

sys.path.insert(0, str(ROOT / "lib/python"))
from jvm_disassembly import methods


def parser_cp(side, tmp):
    (folder,) = (ROOT / "examples").glob("360-*")
    plan = route.resolve(
        folder, read(folder / "example.json"), read(folder / "target.json"), "postorder-" + side
    )
    ready = route.prepare_revision(plan, side, tmp, {})
    entries = runtime._checked(tmp, ready)
    return [tmp / p.path for role in ("adapter", "original", "dependency") for p in entries if p.role == role]


def setup_line(key, value):
    return (
        f"System.clearProperty({java_string(key)});"
        if value is None
        else f"System.setProperty({java_string(key)},{java_string(value)});"
    )


def prepare(family, side, tmp, frozen):
    if family == "xz":
        key = "org.tukaani.xz.ArrayCache"
        owner = key
        cp = paths("commons-compress-767", side, frozen)
        folder = EXTERNAL / "scenarios/commons-compress-767"
        harness = tmp / "UpgradeCallerClaim.java"
        harness.write_text(caller_source("UpgradeProbe", read(folder / "scope.json")["cases"]))
        sources = [folder / "UpgradeProbe.java", harness]
        values = {"absent": None, "dummy": "Dummy", "basic": "Basic", "bogus": "Bogus"}
        calls = {"frame": "UpgradeCallerClaim.matches(selector)"}
    else:
        key = "line.separator"
        owner = "com.github.javaparser.utils.LineSeparator"
        cp = parser_cp(side, tmp / "prepared")
        sources = [ROOT / "lib/benchmark/domain-foundations/SeparatorInputs.java"]
        values = {"absent": None, "lf": "\n", "crlf": "\r\n"}
        calls = {k: f"organic.TreeOrder.{k}(selector)==1" for k in ("postorder", "preorder", "terminal")}
        calls["nonempty"] = "organic.TreeOrder.postorder(selector)==1"
    parts = ["public final class PropertyProfiles {"]
    entries = {}
    for label, value in values.items():
        set_value = setup_line(key, value)
        for name, expression in calls.items():
            method = label + name.capitalize()
            parts.append(
                f"public static boolean {method}(int selector) {{ {set_value} return {expression}; }}"
            )
            entries[method] = {
                "key": key,
                "value": value,
                "claim": name,
                "profile": label,
                "args": 4 if family == "xz" else 2,
                "firstSelector": int(name == "nonempty"),
            }
        if family == "xz" and label != "bogus":
            want = (
                "org.tukaani.xz.BasicArrayCache.getInstance()"
                if label == "basic"
                else "org.tukaani.xz.ArrayCache.getDummyCache()"
            )
            method = label + "Cache"
            parts.append(
                f"public static boolean {method}() {{ {set_value} return org.tukaani.xz.ArrayCache.getDefaultCache()=={want}; }}"
            )
            entries[method] = {
                "key": key,
                "value": value,
                "claim": "cache identity",
                "profile": label,
                "args": 0,
            }
    if family == "xz":
        set_value = setup_line(key, "Bogus")
        parts.append(f"""public static boolean erroneous() {{
            {set_value}
            try {{ org.tukaani.xz.ArrayCache.getDefaultCache(); return false; }}
            catch (Error first) {{
                if (first.getClass()!=Error.class) return false;
                try {{ org.tukaani.xz.ArrayCache.getDefaultCache(); return false; }}
                catch (NoClassDefFoundError second) {{ return true; }}
            }}
        }}""")
        entries["erroneous"] = {
            "key": key,
            "value": "Bogus",
            "claim": "first Error and subsequent NoClassDefFoundError",
            "profile": "bogus",
            "args": 0,
        }
    else:
        parts.append("""public static boolean erroneous() {
            System.clearProperty("line.separator");
            try { com.github.javaparser.utils.LineSeparator.SYSTEM.asRawString(); return false; }
            catch (ExceptionInInitializerError first) {
                if (!(first.getCause() instanceof NullPointerException)) return false;
                try { com.github.javaparser.utils.LineSeparator.SYSTEM.asRawString(); return false; }
                catch (NoClassDefFoundError second) { return true; }
            }
        }""")
        entries["erroneous"] = {
            "key": key,
            "value": None,
            "claim": "first ExceptionInInitializerError and subsequent NoClassDefFoundError",
            "profile": "absent",
            "args": 0,
        }
        for name in calls:
            target = "postorder" if name == "nonempty" else name
            parts.append(
                f"public static boolean bounded{name.capitalize()}(int selector, char first, char second, int length) {{"
                f"return foundation.SeparatorInputs.{target}(selector,first,second,length)==1; }}"
            )
    source = tmp / "PropertyProfiles.java"
    source.write_text("\n".join(parts) + "\n}\n")
    classes = tmp / "classes"
    classes.mkdir()
    command(
        [
            JDK / "bin/javac",
            "-g",
            "-parameters",
            "-proc:none",
            "-cp",
            os.pathsep.join(map(str, cp)),
            "-d",
            classes,
            source,
            *sources,
        ]
    )
    return [classes, *cp], owner, entries


def run(family, out=None):
    out = out or RESULTS / "transfer" / family
    out.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    frozen = read(RESULTS / "scope.json")
    data = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checkerSha256": sha(checker),
        "sides": {},
    }
    if family == "xz":
        data["ordinary"] = upgrade("commons-compress-767", out, frozen)
    for side in (("old", "new") if family == "xz" else ("parent", "fix")):
        with tempfile.TemporaryDirectory() as work:
            tmp = Path(work)
            tools = compiler(tmp)
            cp, owner, entries = prepare(family, side, tmp, frozen)
            subject = inventory(checker, cp, owner + "#<clinit>")
            from investigate import class_bytes

            body = tmp / "Initializer.class"
            body.write_bytes(class_bytes(subject["binding"]))
            table, _ = methods(JDK / "bin/javap", body)
            pcs = [
                i.pc
                for i in table["<clinit>", "()V"]["code"]
                if i.op == "invokestatic" and "java/lang/System.getProperty:" in i.member
            ]
            if not pcs:
                raise ValueError("the original initializer has no selected property read")
            result = {}
            for name, e in entries.items():
                args = e["args"]
                entry = inventory(checker, cp, "PropertyProfiles#" + name)
                runs = {}
                for selector in range(e.get("firstSelector", 0), max(1, args)):
                    arguments = [str(selector)] if args else []
                    lines = original(tools, cp, subject, {"pc": pcs[0], "kind": "call"}, entry, arguments)
                    if not any(s.startswith("hit ") for s in lines):
                        raise ValueError(("property read not witnessed", name, lines))
                    runs[str(selector)] = lines
                r = native(
                    checker,
                    cp,
                    "PropertyProfiles#" + name,
                    f"selector >= {e.get('firstSelector', 0)} && selector < {args}" if args else None,
                    64 if family == "xz" else 96,
                    128 if family == "xz" else 64,
                    60,
                    tmp / ("native-" + name),
                )
                result[name] = {**e, "native": r, "originalJvm": runs}
                if name == "erroneous" and runs["0"][-1] != "returned true":
                    raise ValueError(runs)
                if e["claim"] == "cache identity" and runs["0"][-1] != "returned true":
                    raise ValueError(runs)
                if (
                    family == "xz"
                    and e["claim"] == "frame"
                    and any(
                        lines[-1] != ("returned false" if e["profile"] == "bogus" else "returned true")
                        for lines in runs.values()
                    )
                ):
                    raise ValueError((side, name, runs))
            ordinary_witnesses = {}
            bounded = {}
            if family == "javaparser":
                for name in ("postorder", "terminal", "preorder", "nonempty"):
                    assumption = (
                        f"selector >= {int(name == 'nonempty')} && selector < 2 && length >= 0 && length <= 2"
                    )
                    entry = "PropertyProfiles#bounded" + name.capitalize()
                    bounded[name] = native(
                        checker, cp, entry, assumption, 96, 64, 60, tmp / ("bounded-" + name)
                    )
                for name in ("postorder", "terminal", "preorder"):
                    entry = inventory(checker, cp, "organic.TreeOrder#" + name)
                    gate = {"kind": "call", "pc": pcs[0]}
                    outcomes = [original(tools, cp, subject, gate, entry, [str(i)]) for i in range(2)]
                    ordinary_witnesses[name] = outcomes
            data["sides"][side] = {
                "boundClassSha256": subject["binding"]["sha256"],
                "propertyReadPcs": pcs,
                "profiles": result,
                "boundedNonNullSeparator": bounded,
                "ordinaryUnmodifiedJvm": ordinary_witnesses,
                "classpath": [sha(p) for p in cp[1:] if p.is_file()],
            }
    write(out / "measurement.json", data)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("family", choices=("xz", "javaparser"))
    p.add_argument("--output", type=Path, help="write this repeat to a separate receipt directory")
    args = p.parse_args()
    run(args.family, args.output)
