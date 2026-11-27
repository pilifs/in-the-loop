"""Run the two original Maven plugins through their upstream Maven integration harness."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
PINS = {"parent":"d34a479879d348a1758196b7d1c696ea4f8ea8f0", "fix":"69ad59c413ec8dfbd884ba0e712e8ada89513d29"}


def local_mirror(cache, destination):
    """Maven layout for the immutable archives already present in the prepared offline caches."""
    for src in (cache / "m2").rglob("*"):
        if src.is_file() and src.suffix in (".jar",".pom",".xml"):
            out = destination / src.relative_to(cache/"m2")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.symlink_to(src)
    modules = cache / "gradle-home/caches/modules-2/files-2.1"
    for src in modules.glob("*/*/*/*/*"):
        if src.suffix not in (".jar", ".pom", ".module", ".zip") or not src.is_file():
            continue
        group,artifact,version,_,filename = src.relative_to(modules).parts
        if "SNAPSHOT" in version:
            continue
        if src.suffix == ".pom" and hashlib.sha1(src.read_bytes()).hexdigest() != src.parent.name.zfill(40):
            raise ValueError("retained POM differs from its Gradle content address: " + filename)
        out = destination.joinpath(*group.split("."),artifact,version,filename)
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.symlink_to(src)


def run(side, preflight):
    cache = Path(os.environ.get("SPRING_BOOT_S_CACHE", Path.home()/".cache/in-the-loop/spring-boot-pr-links-s01-s50"))
    source = cache / ("worktrees/S48-" + side)
    ref = subprocess.check_output(["git","-C",source,"rev-parse","HEAD"],text=True).strip()
    if ref != PINS[side]:
        raise ValueError("wrong upstream revision")
    gradle = cache / "tools/gradle-9.7.0/bin/gradle"
    module = Path("build-plugin/spring-boot-maven-plugin")
    harness = module / "src/intTest/java/org/springframework/boot/maven"
    if not gradle.exists() or not (source/harness/"MavenBuildExtension.java").is_file():
        raise ValueError("missing original Maven plugin harness")
    if preflight:
        return {"revision":ref,"gradle":gradle.parent.parent.name}
    temp_root = Path(os.environ.get("TMPDIR") or cache / "tmp")
    if not temp_root.resolve().is_relative_to(Path.home()/".cache/in-the-loop"):
        temp_root = cache / "tmp"
    with tempfile.TemporaryDirectory(prefix="boot-maven-war-",dir=temp_root) as tmp:
        work = Path(tmp)
        tree = work / "tree"
        tree.mkdir()
        with subprocess.Popen(["git","-C",source,"archive",ref],stdout=subprocess.PIPE) as export:
            with tarfile.open(fileobj=export.stdout,mode="r|") as archive:
                archive.extractall(tree,filter="data")
        if export.returncode:
            raise RuntimeError("source export failed")
        shutil.copyfile(HERE/"MavenWarObservation.java",tree/harness/"MavenWarObservation.java")
        fixture = tree/module/"src/intTest/projects/verified-sbom"
        fixture.mkdir()
        shutil.copyfile(HERE/"pom.xml",fixture/"pom.xml")
        local = work/"public-mirror"
        local_mirror(cache,local)
        resolver = tree/"buildSrc/src/main/java/org/springframework/boot/build/bom/BomResolver.java"
        original_resolver = resolver.read_text()
        hook = "private File resolveBom(String coordinates) {"
        if original_resolver.count(hook) != 1:
            raise ValueError("unexpected upstream BOM resolver")
        # The detached @pom resolution is sticky to its earlier repository, even with
        # a second local repository. Use the exact retained GAV at that read boundary.
        resolver.write_text(original_resolver.replace(hook, hook + """
        String[] gav = coordinates.split(":");
        if (gav.length == 3 && !gav[2].contains("SNAPSHOT")) {
            File retained = new File(System.getenv("BOOT_S48_MIRROR_PATH"),
                gav[0].replace('.', '/') + "/" + gav[1] + "/" + gav[2] + "/" + gav[1] + "-" + gav[2] + ".pom");
            if (retained.isFile()) {
                return retained;
            }
        }
"""))
        # Gradle's offline metadata is keyed by the repository that first supplied a file.
        # The original BOM POMs are already cached, and a file repository can resolve them
        # even when the earlier integration build fetched them from another repository.
        gradle_init = work/"cached-boms.gradle"
        gradle_init.write_text("""
beforeProject { p ->
    p.repositories.maven {
        name = 'retainedReleaseBoms'
        url = uri(System.getenv('BOOT_S48_MIRROR'))
        mavenContent { releasesOnly() }
        content {
            includeModuleByRegex '.*', '.*(bom|BOM|dependencies|platform).*'
            includeModule 'org.apache.maven', 'apache-maven'
        }
        metadataSources { mavenPom(); artifact() }
    }
}
""")
        settings = tree/module/"src/intTest/projects/settings.xml"
        original = settings.read_text()
        if "<mirrors>" in original:
            raise ValueError("upstream Maven mirror settings changed")
        mirror = f"<mirrors><mirror><id>cached-public</id><mirrorOf>external:*</mirrorOf><url>{local.as_uri()}</url></mirror></mirrors>"
        settings.write_text(original.replace("</settings>", mirror + "\n</settings>"))
        receipts = work/"readbacks"
        receipts.mkdir()
        jdks = Path.home()/".sdkman/candidates/java"
        names = ("8.0.512.0+9-tem","11.0.33.0+10-tem","17.0.21.0+9-tem","21.0.13.0+9-tem","25.0.5.0+8-tem")
        env = {**os.environ,"JAVA_HOME":str(jdks/names[-1]),"GRADLE_USER_HOME":str(work/"gradle"),
               "GRADLE_RO_DEP_CACHE":str(cache/"gradle-home/caches"),"BOOT_S48_RECEIPTS":str(receipts),
               "BOOT_S48_MIRROR":local.as_uri(),"BOOT_S48_MIRROR_PATH":str(local)}
        cmd = [gradle,"--offline","-I",gradle_init,"--console=plain","--no-daemon","--no-build-cache","--no-scan","--max-workers=3",
               "-Dorg.gradle.jvmargs=-Xmx2g -XX:ActiveProcessorCount=3","-Pkotlin.compiler.execution.strategy=in-process",
               "-Porg.gradle.java.installations.auto-detect=false","-Porg.gradle.java.installations.auto-download=false",
               "-Porg.gradle.java.installations.paths=" + ",".join(str(jdks/n) for n in names),
               "-x",":buildSrc:test","-x",":buildSrc:checkstyleMain","-x",":buildSrc:checkstyleTest","-x",":buildSrc:checkFormat",
               ":build-plugin:spring-boot-maven-plugin:intTest","--tests","org.springframework.boot.maven.MavenWarObservation"]
        log = subprocess.run(cmd, cwd=tree,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1200)
        if log.returncode:
            print(log.stdout[-4400:])
            for detail in (tree/module/"build/test-results/intTest").glob("*.xml"):
                import xml.etree.ElementTree as ET
                for node in ET.parse(detail).iter("failure"):
                    print((node.get("message") or "")[-2800:])
            raise RuntimeError("original Maven integration build failed")
        rows = {}
        for path in receipts.glob("*.txt"):
            name,fmt,loc,payload,order = path.read_text().splitlines()
            row = dict(format=fmt,location=loc,payload=payload,decoyBeforeSbom=order)
            if name in rows and row != rows[name]:
                raise ValueError("Maven versions disagreed")
            rows[name] = row
        if set(rows) != {"intent","challenge"}:
            raise ValueError("Maven did not return both physical WAR observations")
        return {"revision":ref,"observations":rows,"mavenBuilds":len(list(receipts.glob("*.txt")))}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("side", choices=PINS)
    p.add_argument("--check-inputs", action="store_true")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = run(args.side,args.check_inputs)
    print(json.dumps(result,sort_keys=True))
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+"\n")
