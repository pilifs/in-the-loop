"""Run the unchanged landed DateFormattingTests method on each historical registrar slice."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from measure import ROOT, SETUP, digest, read, run_cmd, seed, write
from targets import route, runtime, runtime_jdk, runtime_maven, sidecar

CASE = ROOT / "examples/374-spring-formatter-binding"
SUITE = "org.springframework.format.datetime.DateFormattingTests"
TEST = "testBindDateAnnotatedPatternWithGlobalFormat"
TEST_FILE = Path("spring-context/src/test/java") / (SUITE.replace(".", "/") + ".java")
TOOLS = {"org.junit.platform:junit-platform-console-standalone:1.5.2": "423e2516cbf393c0c78300769601f6c64d374a7bfb41e55d3655e538deb5d075",
         "org.assertj:assertj-core:3.14.0": "ae84617817b71eb834a14c0bdeb8af2b495dcf3ed64ed6ef5c9a7732ca9cf110"}


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT", str(SETUP / "src"))
    seed(CASE)
    example = read(CASE / "example.json")
    spec = sidecar.load(CASE, example)
    jdk = Path(runtime_jdk.home("21"))
    with tempfile.TemporaryDirectory(prefix="historical-date-test-") as tmp:
        work = Path(tmp)
        compiler, java = (jdk / "bin" / name for name in ("javac", "java"))
        tools = []
        for coords, sha in TOOLS.items():
            destination = work / (coords.split(":")[1] + ".jar")
            item = runtime_maven.check_item(dict(coordinates=coords, sha256=sha), "test dependency")
            runtime_maven.acquire(item, destination, runtime_maven.Cache(), network=True)
            tools.append(destination)
        report = {"test": SUITE+"#"+TEST, "jdk": runtime_jdk.release(jdk), "tools": TOOLS, "sides": {}}
        for side in ("landed", "parent"):
            plan = route.resolve(CASE, example, spec, "annotated-"+side)
            stage = work / side
            prepared = runtime.prepare(plan, side, stage)
            if prepared.stage != "artifacts-ready":
                raise ValueError(f"{side}: {prepared.diagnostic}")
            test = work / "landed/checkout" / TEST_FILE
            source_hash = digest(test)
            if report.setdefault("landedTestSha256", source_hash) != source_hash:
                raise ValueError("different original regression on the two sides")
            library = [stage / p for p in prepared.classpath]
            classes = work / ("tests-"+side)
            classes.mkdir()
            cp = os.pathsep.join(map(str,[*library,*tools]))
            subprocess.run([compiler, "-proc:none", "-cp", cp, "-d", classes, test], check=True)
            facts = prepared.source["target"]
            xmls = work / ("xml-"+side)
            cost = run_cmd([java,"-Xmx256m","-Duser.timezone=UTC","-Duser.language=en","-Duser.country=US",
                            "-cp",os.pathsep.join(map(str,[classes,*library,*tools])),
                            "org.junit.platform.console.ConsoleLauncher","--disable-ansi-colors","--details=none",
                            "--reports-dir",str(xmls),"--select-method",SUITE+"#"+TEST],out / (side+".log"))
            root = ET.parse(xmls / "TEST-junit-jupiter.xml").getroot()
            row, = root.findall("testcase")
            failure = row.find("failure")
            if (root.get("tests") != "1" or root.get("errors") != "0" or row.get("classname") != SUITE
                    or row.get("name") != TEST+"()" or (failure is not None) != (side == "parent")
                    or cost["exit"] != int(side == "parent")):
                raise ValueError(f"{side}: unexpected historical JUnit outcome")
            if failure is not None:
                message = failure.get("message", "")
                if "1" not in message or "0" not in message:
                    raise ValueError("parent failed on another assertion")
            # Preserve the assertion and its stack without environmental XML properties.
            path = out / (side+"-testcase.xml")
            ET.ElementTree(row).write(path, encoding="utf-8", xml_declaration=True)
            report["sides"][side] = dict(commit=prepared.commit, scope="historical registrar source slice",
                result="failed assertion" if failure is not None else "passed", xml=path.name, xmlSha256=digest(path),
                target=facts, orderedJars=[digest(p) for p in library], cost=cost)
        write(out / "measurement.json", report)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True)
    run(cli.parse_args().output)
