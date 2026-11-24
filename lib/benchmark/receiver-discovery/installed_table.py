"""Check explicit live-table roots and retry the original Configuration callers from those prestates."""

import argparse
import os
from pathlib import Path
import tempfile

from callers import RESULTS, read, sha
from configuration import prepare
from investigate import compiler, native, write
from recovery import HERE, OUT, compile_to, identities, java, property_reads


def summary(row):
    return {k: row[k] for k in ("verdict", "problem", "assume", "assert", "counterexample", "stated", "target")}


def measure(case):
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    result = {**identities(), "checkerSha256": sha(checker), "rows": {}}
    scope = read(RESULTS / "scope.json")
    for side in (["control"] if case == "controls" else ["old", "new"]):
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            if side == "control":
                classes = temp / "classes"
                classes.mkdir()
                compile_to(classes, [classes], HERE / "history/InstalledProperties.java")
                cp = [classes]
                targets = {name: expected for name, expected in [
                    ("liveIdentity", True), ("wrongIdentity", False), ("ownAndInherited", True),
                    ("nonStringPrevious", True), ("unknownTableEmpty", False)]}
                owner = "InstalledProperties"
                guard = None
                args = [[]]
            else:
                cp, _ = prepare(case, side, temp, scope)
                prop = property_reads(checker, cp, temp)
                # The key is derived from the selected original's ldc instructions.
                from targets.upgrade_receiver import java_string
                key = java_string(prop["key"])
                owner = "InstalledCaller"
                code = temp / (owner + ".java")
                code.write_text(f"""import java.util.Properties;
public class InstalledCaller {{
    public static boolean empty(int selector) {{
        System.setProperties(new Properties());
        return UpgradeCallerClaim.matches(selector);
    }}
    public static boolean own(int selector) {{
        Properties parent = new Properties();
        parent.setProperty({key}, "_");
        System.setProperties(parent);
        return UpgradeCallerClaim.matches(selector);
    }}
    public static boolean inherited(int selector) {{
        Properties parent = new Properties();
        parent.setProperty({key}, "_");
        System.setProperties(new Properties(parent));
        return UpgradeCallerClaim.matches(selector);
    }}
}}
""")
                # Keep all unrelated bootstrap properties at their stock settings for the ordinary
                # comparisons in recovery.py. These three explicit table replacements are controls.
                from callers import JDK
                from investigate import command
                command([JDK / "bin/javac", "-proc:none", "-g", "-parameters", "-cp",
                         os.pathsep.join(map(str, cp)), "-d", cp[0], code])
                targets = dict.fromkeys(("empty", "own", "inherited"))
                args = [[str(i)] for i in range(4)]
                guard = scope["registeredCallers"][case]["assume"]
            tools = compiler(temp)
            rows = {}
            for name, expected in targets.items():
                output = []
                desc = "(I)Z" if guard else "()Z"
                for values in args:
                    observed = java([tools, *cp], "org.intheloop.observation.CallOnce", owner, owner, name, desc, *values)
                    if observed[0] != "class " + sha(cp[0] / (owner + ".class")):
                        raise ValueError("original entry bytes differ")
                    output.append(observed[-1])
                if expected is not None and output != ["returned " + str(expected).lower()]:
                    raise ValueError((name, output))
                attempt = native(checker, cp, owner + "#" + name, guard, 64, 128, 60, temp / name)
                if attempt["verdict"] == "verified" and any(v != "returned true" for v in output):
                    raise ValueError(("positive contradicts original JVM", name, output))
                if case == "controls" and name in ("liveIdentity", "wrongIdentity") and attempt["verdict"] != (
                        "verified" if expected else "violation"):
                    raise ValueError((name, attempt["verdict"], attempt["problem"]))
                rows[name] = {"jvm": output, "native": summary(attempt)}
            result["rows"][side] = rows
    out = OUT / "installed-properties"
    out.mkdir(parents=True, exist_ok=True)
    write(out / (case + ".json"), result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", choices=["controls", "commons-configuration-565", "commons-configuration-601"])
    measure(p.parse_args().case)
