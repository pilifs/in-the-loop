"""Exercise the original Gradle plugin in small independent consumer builds, entirely offline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from workspace import scratch


def sha(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def gradle(work, installation, jdk, *tasks):
    log = subprocess.run([installation / "bin/gradle", "--offline", "--console=plain", "--no-build-cache",
                          "--max-workers=2", "--gradle-user-home", work.parent / "gradle-home", *tasks],
                         cwd=work, env={**os.environ, "JAVA_HOME": str(jdk)}, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    if log.returncode:
        raise RuntimeError("Gradle build failed: " + log.stdout[-2800:])
    return log.stdout


def project(work, plugin):
    work.mkdir()
    (work / "settings.gradle").write_text("rootProject.name = 'fixture'\n")
    (work / "gradle.properties").write_text("org.gradle.jvmargs=-Xmx512m -XX:ActiveProcessorCount=2\norg.gradle.daemon.idletimeout=15000\n")
    (work / "plugin-files.txt").write_text("\n".join(map(str, plugin)) + "\n")
    return """buildscript { dependencies { classpath files(file('plugin-files.txt').readLines()) } }
apply plugin: 'java'
apply plugin: 'org.springframework.boot'
"""


def config_source(work, name, prefix, description):
    directory = work / "src/main/java/fixture"
    directory.mkdir(parents=True, exist_ok=True)
    comment = f"    /** {description} */\n" if description else ""
    (directory / (name + ".java")).write_text(
        "package fixture;\nimport org.springframework.boot.context.properties.ConfigurationProperties;\n"
        + f'@ConfigurationProperties("{prefix}")\npublic class {name} {{\n' + comment
        + "    private String someProperty;\n    public String getSomeProperty() { return someProperty; }\n"
        + "    public void setSomeProperty(String value) { this.someProperty = value; }\n}\n")


def metadata(work, install, jdk, base, processor, annotation):
    (work / "build.gradle").write_text(base + """
dependencies {
    implementation files(file('annotation-file.txt').text.trim())
    annotationProcessor files(file('processor-file.txt').text.trim())
}
tasks.withType(JavaCompile).configureEach { options.compilerArgs.add('-verbose') }
""")
    (work / "annotation-file.txt").write_text(str(annotation))
    (work / "processor-file.txt").write_text(str(processor))
    config_source(work, "SomeProperties", "some", "Original description.")
    config_source(work, "MoreProperties", "more", "Before edit.")
    def build(clean):
        log = gradle(work, install, jdk, *(("clean", "compileJava") if clean else ("compileJava",)))
        parsed = sorted({name for line in log.splitlines() if "[parsing started" in line
                         for name in ("SomeProperties", "MoreProperties") if name + ".java" in line})
        if parsed != (["MoreProperties", "SomeProperties"] if clean else ["MoreProperties"]):
            raise ValueError(f"javac source scope {parsed} (clean={clean})")
        path = work / "build/classes/java/main/META-INF/spring-configuration-metadata.json"
        properties = {p["name"]: p.get("description") for p in json.loads(path.read_text())["properties"]}
        return {"parsed": parsed, "some": properties["some.some-property"], "more": properties["more.some-property"]}
    initial = build(True)
    config_source(work, "MoreProperties", "more", "Edited description.")
    warm = build(False)
    clean = build(True)
    config_source(work, "MoreProperties", "more", None)
    removed = build(False)
    removed_clean = build(True)
    return dict(initial=initial, editedIncremental=warm, editedClean=clean, removedIncremental=removed,
                removedClean=removed_clean)


def layer_owner(index, name):
    found = []
    layer = None
    for line in index.splitlines():
        group = re.fullmatch(r'- "([^"]+)":', line)
        entry = re.fullmatch(r'  - "([^"]+)"', line)
        if group:
            layer = group[1]
        elif entry and (name == entry[1] or entry[1].endswith("/") and name.startswith(entry[1])):
            found.append(layer)
    if len(found) != 1:
        raise ValueError(f"{name}: expected one owner, found {found}")
    return found[0]


def layers(work, install, jdk, base):
    sources = {"org/example/Open": "public static void main(String[] args) {}", "org/example/internal/Hidden": "", "other/Third": ""}
    def write_source(name,body):
        path = work / "src/main/java" / (name + ".java")
        path.parent.mkdir(parents=True, exist_ok=True)
        pkg, cls = name.rsplit("/", 1)
        path.write_text(f"package {pkg.replace('/', '.')}; public class {cls} {{ {body} }}\n")
    for name, body in sources.items():
        if name != "other/Third":
            write_source(name,body)
    modes = {"intent": "exclude 'org/example/internal/**'", "control": "include 'org/example/internal/**'",
             "challenge": "include 'org/example/**'\n                exclude 'org/example/internal/**'"}
    records = {}
    for mode, rule in modes.items():
        if mode == "challenge":
            write_source("other/Third",sources["other/Third"])
        (work / "build.gradle").write_text(base + """
springBoot { mainClass = 'org.example.Open' }
tasks.named('bootJar') {
    includeTools = false
    layered {
        application {
            intoLayer('public') { RULE }
            intoLayer('rest')
        }
        dependencies { intoLayer('libs') }
        layerOrder = ['public', 'rest', 'libs']
    }
}
""".replace("RULE", rule))
        gradle(work, install, jdk, "clean", "bootJar")
        jar, = (work / "build/libs").glob("*.jar")
        with ZipFile(jar) as archive:
            index = archive.read("BOOT-INF/layers.idx").decode()
            result = {}
            for name in sources:
                entry = "BOOT-INF/classes/" + name + ".class"
                if name == "other/Third" and mode != "challenge":
                    if entry in archive.namelist():
                        raise ValueError("challenge-only class present in baseline")
                    continue
                if archive.namelist().count(entry) != 1 or archive.read(entry) != (work / "build/classes/java/main" / (name + ".class")).read_bytes():
                    raise ValueError("packaged bytes differ for " + entry)
                result[name] = layer_owner(index, entry)
            records[mode] = result
    return records


def main(case, output, check):
    lock = json.loads((HERE / "inputs.json").read_text())
    cache = Path(os.environ.get("SPRING_BOOT_S_CACHE", Path.home() / ".cache/in-the-loop/spring-boot-pr-links-s01-s50"))
    jdk = Path.home() / ".sdkman/candidates/java" / lock["jdk"]
    if sha(jdk / "release") != lock["jdkRelease"]:
        raise ValueError("wrong build JDK")
    spec = lock["cases"][case]
    install = cache / "tools" / ("gradle-" + spec["gradle"])
    if sha(install / "lib" / ("gradle-launcher-" + spec["gradle"] + ".jar")) != spec["launcher"]:
        raise ValueError("wrong Gradle launcher")
    results = {}
    for side in ("parent", "fix"):
        row = spec["sides"][side]
        files = list(row["plugin"]) + [v for k,v in row.items() if k != "plugin"]
        if any(sha(cache / n) != lock["sha256"][n] for n in files):
            raise ValueError(case + " " + side + " deployment changed")
        with ZipFile(cache / row["plugin"][0]) as jar:
            jar.getinfo("META-INF/gradle-plugins/org.springframework.boot.properties")
        if check:
            print(case, side, "verified", len(files), "inputs")
            continue
        with scratch("boot-gradle-") as tmp:
            work = Path(tmp) / "fixture"
            base = project(work, [cache / n for n in row["plugin"]])
            results[side] = (metadata(work,install,jdk,base,cache/row["processor"],cache/row["annotation"])
                             if case == "S10" else layers(work,install,jdk,base))
        print(case, side, json.dumps(results[side], sort_keys=True), flush=True)
    if output and not check:
        output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("S10","S47"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-inputs", action="store_true")
    args = parser.parse_args()
    main(args.case,args.output,args.check_inputs)
