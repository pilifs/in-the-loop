"""Apply each pinned, compiled named-action method to the same published Gradle 7.6 runtime."""
import argparse
from copy import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
CORE = "org/gradle/api/internal/AbstractTask"
ZIP_HASH = "7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(cache, dest):
    pins = json.loads((HERE.parent / "comparison.json").read_text())["revisions"]
    zip_path = cache / "dl/gradle-D/gradle-7.6-bin.zip"
    if sha(zip_path) != ZIP_HASH:
        raise ValueError("Gradle 7.6 distribution digest differs")
    dist = cache / "tools/gradle-7.6"
    jdk = Path.home() / ".sdkman/candidates/java/17.0.21.0+9-tem/bin"
    src_path = "subprojects/core/src/main/java/org/gradle/api/internal/"
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gradle-action-") as tmp, ZipFile(zip_path) as release:
        work = Path(tmp)
        # Check each compiler dependency against the published distribution before using it.
        for member in release.namelist():
            if member.startswith("gradle-7.6/lib/") and member.endswith(".jar"):
                local = dist / member.split("/", 1)[1]
                if sha(local) != hashlib.sha256(release.read(member)).hexdigest():
                    raise ValueError("Gradle support differs: " + local.name)
        cp = os.pathsep.join(str(dist / tail) for tail in ("lib/*", "lib/plugins/*"))
        subprocess.run([jdk/"javac", "-proc:none", "-cp", cp, "-d", work, HERE/"ReplaceMethod.java"], check=True)
        core_jar = dist / "lib/gradle-core-7.6.jar"
        with ZipFile(core_jar) as baseline:
            name = CORE + ".class"
            original = work / "release.class"
            original.write_bytes(baseline.read(name))
            for side, pin in pins.items():
                tree = cache / f"worktrees/L15-gradle-{side}"
                build = work / side
                build.mkdir()
                sources = []
                for cls in ("AbstractTask", "TaskInternal"):
                    src = build / (cls + ".java")
                    src.write_bytes(subprocess.check_output(["git", "-C", tree, "show", f"{pin}:{src_path}{src.name}"]))
                    sources.append(src)
                subprocess.run([jdk/"javac", "--release", "8", "-g", "-proc:none", "-cp", cp,
                                "-d", build, *sources], check=True)
                patched = build / "patched.class"
                subprocess.run([jdk/"java", "-cp", str(work) + os.pathsep + cp, "ReplaceMethod",
                                original, build / name, patched], check=True)
                staged = build / "gradle-core.jar"
                with ZipFile(staged, "w") as output:
                    for info in baseline.infolist():
                        output.writestr(copy(info), patched.read_bytes() if info.filename == name else baseline.read(info))
                target = dest / f"L15-named-action-{side}.jar"
                if target.exists() and sha(staged) != sha(target):
                    raise ValueError(f"{target} already contains a different build")
                if not target.exists():
                    with tempfile.NamedTemporaryFile(dir=dest) as temporary:
                        shutil.copyfile(staged, temporary.name)
                        try:
                            os.link(temporary.name, target)
                        except FileExistsError:
                            if sha(target) != sha(staged):
                                raise ValueError(f"concurrent build produced a different {target}")
                print(side, pin, "whole compiled class", sha(build / name), "runtime jar", sha(target))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, default=Path.home()/".cache/in-the-loop/merged-pr-links-l01-l20")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    prepare(args.cache, args.output or args.cache/"artifacts")
