"""Compare the registered original callers, their lookup branch and two independent live configurations."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from callers import ASSETS, EXTERNAL, RESULTS, ROOT, JDK, read, sha, upgrade
from investigate import compiler, command, investigate, inventory, native, original, write
from qualification import construct

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets.upgrade_receiver import caller_source, java_string


def paths(key, side, frozen):
    cp = list(
        map(
            Path, (ASSETS / "receivers/cp" / (key + "-" + side + ".cp")).read_text().strip().split(os.pathsep)
        )
    )
    if [sha(p) for p in cp] != frozen["registeredCallers"][key]["sides"][side]["orderedClasspathSha256"]:
        raise ValueError("registered ordered classpath changed")
    return cp


def prepare(key, side, tmp, frozen):
    cp = paths(key, side, frozen)
    src = EXTERNAL / "scenarios" / key
    cases = read(src / "scope.json")["cases"]
    if cases != frozen["registeredCallers"][key]["cases"]:
        raise ValueError("registered arguments differ")
    harness = tmp / "UpgradeCallerClaim.java"
    harness.write_text(caller_source("UpgradeProbe", cases))
    t = "JSONConfiguration" if key.endswith("565") else "YAMLConfiguration"
    documents = [java_string(cases[i]["args"][0]) for i in (0, 1)]
    isolation = tmp / "ConfigurationIsolation.java"
    isolation.write_text(f"""import org.apache.commons.configuration2.{t};
import java.io.StringReader;
public final class ConfigurationIsolation {{
    public static boolean constructed({t} instance) {{ return instance != null; }}
    public static boolean unchanged(boolean backwards) throws Exception {{
        {t} a=new {t}(), b=new {t}();
        if (backwards) {{ b.read(new StringReader({documents[1]})); a.read(new StringReader({documents[0]})); }}
        else {{ a.read(new StringReader({documents[0]})); b.read(new StringReader({documents[1]})); }}
        return "[red, blue]".equals(a.getList(String.class,"colors").toString())
            && "[Ada]".equals(b.getList(String.class,"cfg.name").toString())
            && a.getList(String.class,"cfg.name")==null && b.getList(String.class,"colors")==null;
    }}
    public static boolean confusesTrees(boolean backwards) throws Exception {{ return !unchanged(backwards); }}
}}""")
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
            src / "UpgradeProbe.java",
            harness,
            isolation,
        ]
    )
    return [classes, *cp], t


def measure(key, out):
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    frozen = read(RESULTS / "scope.json")
    out.mkdir(parents=True, exist_ok=True)
    public = upgrade(key, out, frozen)
    result = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checker": sha(checker),
        "registered": public,
        "sides": {},
    }
    for side in ("old", "new"):
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            tools = compiler(tmp)
            cp, t = prepare(key, side, tmp, frozen)
            inv = inventory(checker, cp, "UpgradeProbe#observe")
            entry = inventory(checker, cp, "UpgradeCallerClaim#matches")
            choices = [s for s in inv["sites"] if s["kind"] == "branch" and s["opcode"] in (198, 199)]
            (site,) = choices
            directory = tmp / "lookup"
            directory.mkdir()
            q = investigate(
                checker,
                cp,
                "UpgradeCallerClaim#matches",
                "UpgradeProbe#observe",
                inv["binding"]["sha256"],
                site["pc"],
                "branch",
                "taken",
                "arg0 >= 0 && arg0 < 4",
                64,
                128,
                60,
                out / side / "lookup",
                directory,
                tools,
            )
            jvm = {}
            for i in range(4):
                lines = original(tools, cp, inv, site, entry, [str(i)])
                if "returned true" not in lines or not any(l.startswith("hit ") for l in lines):
                    raise ValueError((key, side, i, lines))
                jvm[str(i)] = lines
            isolation = {}
            for name in ("unchanged", "confusesTrees"):
                trials = []
                for arg in ("false", "true"):
                    lines = command(
                        [
                            JDK / "bin/java",
                            "-ea",
                            "-Xverify:all",
                            "-cp",
                            os.pathsep.join(map(str, [tools, *cp])),
                            "org.intheloop.observation.CallOnce",
                            "ConfigurationIsolation",
                            "ConfigurationIsolation",
                            name,
                            "(Z)Z",
                            arg,
                        ]
                    ).splitlines()
                    if lines[-1] != "returned " + str(name == "unchanged").lower():
                        raise ValueError(lines)
                    trials.append(lines)
                row = native(checker, cp, "ConfigurationIsolation#" + name, None, 64, 128, 60, tmp / name)
                isolation[name] = {"jvm": trials, "native": row}
            p = construct(
                checker,
                "org.apache.commons.configuration2." + t,
                "ConfigurationIsolation#constructed",
                cp,
                tmp / "discovered",
            )
            result["sides"][side] = {
                "originalLookup": jvm,
                "selected": q["disposition"],
                "inventory": inv,
                "isolation": isolation,
                "automatic": p,
                "classpath": frozen["registeredCallers"][key]["sides"][side]["orderedClasspathSha256"],
            }
    write(out / "measurement.json", result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("key", choices=["commons-configuration-565", "commons-configuration-601"])
    a = p.parse_args()
    measure(a.key, RESULTS / "qualification" / a.key)
