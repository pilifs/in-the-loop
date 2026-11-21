"""Read the decisive lines and recorded JVM metadata for two disclosed CI cases from their pinned OCI layers."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
import tarfile
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
LIMIT = 4 * 1024**2


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def members(layer, side, case):
    chosen = {}
    project = case["project"]
    with tarfile.open(layer, "r|gz") as stream:
        for member in stream:
            name = member.name.removeprefix("./")
            if not member.isreg() or name.startswith("/") or ".." in name.split("/") or member.size > LIMIT:
                continue
            if project == "fscrawler" and name.startswith("root/.m2/repository/org/apache/poi/"):
                version = "4.1.2" if side == "pre" else "5.1.0"
                ids = {"poi/4.1.2/poi-4.1.2.jar": "core", f"poi-ooxml/{version}/poi-ooxml-{version}.jar": "ooxml"}
                key = ids.get(name.removeprefix("root/.m2/repository/org/apache/poi/"))
                if key:
                    chosen[key] = (name, stream.extractfile(member).read())
            elif project == "assertj-guava" and name.startswith("root/.m2/repository/org/assertj/assertj-core/"):
                version = "3.22.0" if side == "pre" else "3.23.0"
                if name.endswith(f"/{version}/assertj-core-{version}.pom"):
                    chosen["core-pom"] = (name, stream.extractfile(member).read())
            if name == project + "/" + case["breaking"] + ".log":
                chosen["log"] = (name, stream.extractfile(member).read())
            elif project == "fscrawler" and side == "breaking" and "events" not in chosen and (
                    name.startswith("fscrawler/tika/target/junit4-J0-") and name.endswith(".events")):
                chosen["events"] = (name, stream.extractfile(member).read())
            elif project == "assertj-guava" and side == "pre" and name == (
                    "assertj-guava/target/surefire-reports/TEST-org.assertj.guava.api.Assertions_assertThat_with_Multimap_Test.xml"):
                chosen["xml"] = (name, stream.extractfile(member).read())
            elif name == project + "/pom.xml":
                chosen["pom"] = (name, stream.extractfile(member).read())
    return chosen


def selected_ci(project, side, text):
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        take = line.startswith(("[INFO] BUILD SUCCESS", "[INFO] BUILD FAILURE", "[INFO] Total time:", "[INFO] Finished at:"))
        if project == "fscrawler":
            take |= bool(re.match(r"\[INFO\] (?:FSCrawler Tika \.|Tests summary: 2 suites, 24 tests)", line))
            if side == "breaking":
                take |= any(fragment in line for fragment in ("| TikaDocParserTest.testExtractFromDocx <<<",
                    "| TikaDocParserTest.testDocxWithEmbeddedBadPDF <<<", 'Expected: a string containing "This is a sample',
                    "Expected: not (null or an empty string)", "but: was null", "Failed to extract [100000] characters of text for [/documents/test.docx]:"))
        else:
            take |= any(fragment in line for fragment in ("[INFO] Tests run: 355, Failures:",
                "BannedDependencies failed with message", "Found Banned Dependency:", "enforce (enforce-java-and-dependencies) @ assertj-guava"))
        if take:
            rows.append({"line": number, "text": line})
    return rows


def read(inputs):
    lock = json.loads((HERE / "oci-lock.json").read_bytes())
    result = {}
    for subject, case in lock["cases"].items():
        sides = {}
        for side, item in case["sides"].items():
            layer = inputs / item["localLayer"]
            if digest(layer) != item["layers"][-1]["sha256"] or layer.stat().st_size != item["layers"][-1]["bytes"]:
                raise ValueError("image layer identity mismatch")
            found = members(layer, side, case)
            name, log = found["log"]
            view = {"sourceRevision": case[side], "logImagePath": name, "logSha256": hashlib.sha256(log).hexdigest(),
                    "logBytes": len(log), "ci": selected_ci(case["project"], side, log.decode()),
                    "pomSha256": hashlib.sha256(found["pom"][1]).hexdigest()}
            if subject == "fscrawler":
                shapes = {}
                for role, binary in (("core", "org.apache.poi.extractor.POITextExtractor"),
                                     ("ooxml", "org.apache.poi.ooxml.extractor.POIXMLTextExtractor")):
                    origin, jar = found[role]
                    with zipfile.ZipFile(io.BytesIO(jar)) as entries:
                        raw_class = entries.read(binary.replace(".", "/") + ".class")
                    with tempfile.TemporaryDirectory() as temp:
                        source = Path(temp) / "type.class"
                        source.write_bytes(raw_class)
                        listing = subprocess.check_output(["javap", str(source)], text=True).splitlines()
                    shapes[role] = {"path": origin, "jarSha256": hashlib.sha256(jar).hexdigest(),
                        "classSha256": hashlib.sha256(raw_class).hexdigest(), "declaration": next(l for l in listing if l.startswith("public "))}
                view["poiExtractorTypes"] = shapes
            if "core-pom" in found:
                origin, data = found["core-pom"]
                ns = {"m": "http://maven.apache.org/POM/4.0.0"}
                deps = ET.fromstring(data).findall("m:dependencies/m:dependency", ns)
                view["assertjCorePom"] = {"path": origin, "sha256": hashlib.sha256(data).hexdigest(),
                    "byteBuddy": [{"artifact": dep.findtext("m:artifactId", namespaces=ns),
                                  "scope": dep.findtext("m:scope", "compile", ns), "optional": dep.findtext("m:optional", "false", ns)}
                                 for dep in deps if dep.findtext("m:groupId", namespaces=ns) == "net.bytebuddy"]}
            if "events" in found:
                path, raw = found["events"]
                row, _ = json.JSONDecoder().raw_decode(raw.decode().lstrip())
                if row[0] != "BOOTSTRAP":
                    raise ValueError("missing actual test JVM bootstrap")
                props = row[1]["systemProperties"]
                cp = props["java.class.path"].split(":")
                view["fork"] = {"source": path, "eventsSha256": hashlib.sha256(raw).hexdigest(),
                         "runtime": props["java.runtime.version"], "vendor": props["java.vendor"],
                         "orderedClasspathEntries": len(cp), "orderedClasspathSha256": hashlib.sha256(props["java.class.path"].encode()).hexdigest(),
                         "poi": [p for p in cp if "/org/apache/poi/" in p]}
            if "xml" in found:
                path, xml = found["xml"]
                suite = ET.fromstring(xml)
                props = {p.get("name"): p.get("value") for p in suite.findall("properties/property")}
                view["fork"] = {"source": path, "xmlSha256": hashlib.sha256(xml).hexdigest(),
                            "runtime": props["java.runtime.version"], "vendor": props["java.vendor"], "tests": int(suite.get("tests"))}
            sides[side] = view
        result[subject] = sides
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", type=Path)
    p.add_argument("--output", type=Path)
    opts = p.parse_args()
    value = json.dumps(read(opts.inputs), indent=2, ensure_ascii=False) + "\n"
    if opts.output:
        opts.output.write_text(value)
    else:
        print(value, end="")
