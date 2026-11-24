"""Launch the frozen artifact-only operator without the curator, reference material, host home or network."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CODE=("examples/tools/targets/runtime_jar.py","lib/tools/process_usage.py","lib/python/jvmcontract_io.py",
      "lib/benchmark/beyond-jbmc/blind/auto_upgrade.py","lib/benchmark/beyond-jbmc/blind/ArtifactProbe.java")
GUEST=Path("/tool/lib/benchmark/beyond-jbmc/blind")
JDK=Path.home()/".sdkman/candidates/java/21.0.13.0+9-tem"


def sha(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()


def launch(pair,dest,checker,policy=None,discover=False):
    pair,dest,checker=pair.resolve(),dest.resolve(),checker.resolve()
    if dest.exists(): raise ValueError("an operator work directory already exists")
    if policy:
        for name in CODE:
            if sha(ROOT/name)!=policy["operatorFiles"][name]:raise ValueError("operator differs from freeze")
        if sha(checker)!=policy["checkerSha256"] or sha(JDK/"lib/modules")!=policy["jdkModulesSha256"]:
            raise ValueError("frozen binary or JDK differs")
    dest.mkdir(parents=True)
    (dest/"tmp").mkdir()
    # Materialize only declared classpath files in a read-only mount, including when the caller handed us a larger directory.
    neutral=dest/"inputs";neutral.mkdir()
    spec=json.loads((pair/"inputs.json").read_bytes())
    if set(spec)!={"old","new"}:raise ValueError("operator packet contains unexpected metadata")
    for side in ("old","new"):
        for index,row in enumerate(spec[side]):
            name=f"{side}/{index:03d}.jar"
            if (set(row)!={"path","sha256"} or row["path"]!=name or sha(pair/name)!=row["sha256"]
                    or pair not in (pair/name).resolve().parents):raise ValueError("unbound operator input")
            (neutral/side).mkdir(exist_ok=True)
            shutil.copyfile(pair/name,neutral/name)
    shutil.copyfile(pair/"inputs.json",neutral/"inputs.json")
    output=dest/"output";output.mkdir()
    cmd=["bwrap","--die-with-parent","--new-session","--unshare-user","--unshare-pid","--unshare-net","--unshare-ipc",
         "--unshare-uts","--clearenv","--ro-bind","/usr","/usr","--symlink","usr/bin","/bin","--symlink","usr/lib","/lib",
         "--symlink","usr/lib64","/lib64","--dev","/dev","--proc","/proc","--remount-ro","/proc",
         "--tmpfs","/tmp","--dir","/etc","--ro-bind","/etc/ld.so.cache","/etc/ld.so.cache",
         "--dir","/opt","--ro-bind",str(JDK),"/opt/jdk","--ro-bind",str(checker),"/opt/checker",
         "--ro-bind",str(neutral),"/inputs","--bind",str(output),"/output","--bind",str(dest/"tmp"),"/scratch",
         "--setenv","HOME","/scratch","--setenv","TMPDIR","/scratch","--setenv","JAVA_HOME","/opt/jdk",
         "--setenv","PATH","/opt/jdk/bin:/usr/bin:/bin","--setenv","TZ","UTC","--setenv","LANG","C.UTF-8",
         "--chdir","/scratch"]
    for name in CODE:cmd+=["--ro-bind",str(ROOT/name),"/tool/"+name]
    cmd+=["/usr/bin/python3","-I","-B",str(GUEST/"auto_upgrade.py"),"/inputs","/output/first",
          "--jdk","/opt/jdk","--checker","/opt/checker"]
    if discover:cmd.append("--discover-only")
    with (dest/"operator.log").open("wb") as f:
        run=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    if run.returncode:raise ValueError("isolated operator failed; private diagnostics retained")
    report=json.loads((output/"first/report.json").read_bytes())
    if report["toolSha256"]!=sha(checker) or report["inputs"]!=spec:raise ValueError("operator binding differs")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("pair",type=Path);p.add_argument("dest",type=Path);p.add_argument("checker",type=Path)
    p.add_argument("--lock",type=Path);p.add_argument("--discover-only",action="store_true")
    a=p.parse_args()
    report=launch(a.pair,a.dest,a.checker,json.loads(a.lock.read_bytes()) if a.lock else None,a.discover_only)
    print(len(report["selected"]),"public candidates,",len(report["runs"]),"attempts")
