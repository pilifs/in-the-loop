"""Build and run the pinned Flyway/H2 application with one genuine migration resource per image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from workspace import scratch
MAIN = "fixture.springboot.NativeMigrationApp"
APP = ["--spring.datasource.url=jdbc:h2:mem:migrations", "--spring.datasource.username=sa",
       "--spring.flyway.locations=classpath:db/migration", "--spring.main.banner-mode=off"]
LAYOUTS = {"root": "", "nested": "nested", "deep": "nested/release"}


def sha(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def command(*args, cwd, timeout=90):
    p = subprocess.run([str(arg) for arg in args], cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=timeout)
    if p.returncode:
        print(p.stdout[-4200:], flush=True)
        raise RuntimeError(f"{Path(args[0]).name} exited {p.returncode}")
    return p.stdout


def outcome(log, runtime):
    match = re.findall(r"^MIGRATION runtime=(\w+) version=(\d+) checksum=(-?\d+) row=(\d+)$", log, re.M)
    if len(match) != 1:
        raise ValueError("missing unique Flyway and independent JDBC readback")
    mode, version, checksum, marker = match[0]
    sql = (HERE / "V2__users.sql").read_bytes()
    expected = zlib.crc32(b"".join(sql.splitlines()))
    if expected >= 2**31:
        expected -= 2**32
    if (mode, version, int(checksum), marker) != (runtime, "2", expected, "73"):
        raise ValueError("unexpected migration result " + str(match[0]))
    return dict(runtime=mode, version=version, checksum=int(checksum), row=int(marker), applied=1)


def run(side, layouts, stage):
    inputs = json.loads((HERE / "inputs.json").read_text())
    cache = Path(os.environ.get("SPRING_BOOT_S_CACHE", Path.home() / ".cache/in-the-loop/spring-boot-pr-links-s01-s50"))
    jdk = Path.home() / ".sdkman/candidates/java" / inputs["jdk"]
    if sha(jdk / "release") != inputs["jdkRelease"]:
        raise ValueError("different GraalVM")
    paths = inputs["sides"][side]
    for name in paths:
        if sha(cache / name) != inputs["sha256"][name]:
            raise ValueError("deployment digest mismatch for " + name)
    results = {}
    with scratch("boot-flyway-") as tmp:
        root = Path(tmp)
        classes = root / "classes"
        classes.mkdir()
        dependencies = os.pathsep.join(str(cache / name) for name in paths)
        command(jdk / "bin/javac", "-proc:none", "-parameters", "-cp", dependencies,
                "-d", classes, HERE / "NativeMigrationApp.java", cwd=root)
        for layout in layouts:
            work = root / layout
            app_classes = work / "application"
            shutil.copytree(classes, app_classes)
            target = app_classes / "db/migration" / LAYOUTS[layout] / "V2__users.sql"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HERE / "V2__users.sql", target)
            cp = os.pathsep.join((str(app_classes), dependencies))
            java = jdk / "bin/java"
            print(f"{side} {layout}: JVM application", flush=True)
            jvm = outcome(command(java, "-Xmx384m", "-cp", cp, MAIN, *APP, cwd=work), "jvm")
            record = {"JVM": jvm, "sqlSha256": sha(target)}
            results[layout] = record
            if stage == "jvm":
                continue
            sources, resources, aot_classes = (work / name for name in ("sources", "resources", "aot-classes"))
            for path in (sources, resources, aot_classes):
                path.mkdir()
            command(java, "-Xmx512m", "-cp", cp, "org.springframework.boot.SpringApplicationAotProcessor",
                    MAIN, sources, resources, aot_classes, "fixture", "migration", *APP, cwd=work)
            generated = sorted(sources.rglob("*.java"))
            if not generated:
                raise ValueError("Spring AOT emitted no application sources")
            cp = os.pathsep.join((str(aot_classes), str(resources), cp))
            command(jdk / "bin/javac", "-proc:none", "-cp", cp, "-d", aot_classes, *generated, cwd=work)
            agent = resources / "META-INF/native-image/fixture/migration-agent"
            agent.mkdir(parents=True)
            trained = command(java, "-Xmx512m", "-Dspring.aot.enabled=true",
                              f"-agentlib:native-image-agent=config-output-dir={agent}",
                              "-cp", cp, MAIN, *APP, cwd=work)
            record["AOT JVM"] = outcome(trained, "jvm")
            if stage == "aot":
                continue
            print(f"{side} {layout}: native-image", flush=True)
            image = work / "migration"
            command(jdk / "bin/native-image", "--no-fallback", "--parallelism=4", "-J-Xmx5g",
                    "-O1", "-cp", cp, "-o", image, MAIN, cwd=work, timeout=1500)
            executed = subprocess.run([image, *APP], cwd=work, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, timeout=90)
            if executed.returncode:
                log = executed.stdout
                resource_error = re.search(r"(?i)unable to (?:obtain inputstream|load resource|read)|resource[^\n]*not found|FileNotFoundException", log)
                if side != "parent" or layout == "root" or "V2__users.sql" not in log or "Flyway" not in log or not resource_error:
                    raise RuntimeError("native application failed before the registered result: " + log[-2500:])
                record["native"] = {"outcome": "migration failed", "version": "2", "exitCode": executed.returncode,
                                    "diagnostics": [line.strip()[:250] for line in log.splitlines()
                                                    if "V2__users.sql" in line and "Exception" in line][:3]}
            else:
                record["native"] = outcome(executed.stdout, "native")
            print(json.dumps(record["native"], sort_keys=True), flush=True)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("side", choices=("parent", "fix"))
    p.add_argument("--stage", choices=("jvm", "aot", "native"), default="native")
    p.add_argument("--layouts", choices=LAYOUTS, nargs="+", default=list(LAYOUTS))
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = run(args.side, args.layouts, args.stage)
    print(json.dumps(result, sort_keys=True))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
