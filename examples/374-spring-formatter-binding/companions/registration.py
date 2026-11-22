"""Check the original formatter registrar's ordered effects on a recording FormatterRegistry."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "lib/benchmark/spring-java-data"))
from measure import SETUP, digest, read, seed, write
from targets import class_binding, route, runtime, runtime_jdk, sidecar
sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import PROFILE, invocation, proof

METHOD = "springwork.RegistrationTrace#sequence"
GUARD = "code >= 0 && code <= 1"
ROOTS = ["org.springframework.format.datetime.DateFormatter",
         "org.springframework.format.datetime.DateTimeFormatAnnotationFormatterFactory"]

def run(out, *, physical_only=False, probe=False):
    os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT", str(SETUP / "src"))
    seed(FOLDER)
    example = read(FOLDER / "example.json")
    spec = sidecar.load(FOLDER, example)
    jdk = Path(runtime_jdk.home("21"))
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk/"bin") + os.pathsep + os.defpath)
    for side in (["parent"] if probe else ["parent","landed"]):
        dest = out / side
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="registrar-callbacks-") as tmp:
            work = Path(tmp)
            prep = work / "subject"
            plan = route.resolve(FOLDER, example, spec, "annotated-"+side)
            original = runtime.prepare(plan, side, prep)
            if original.stage != "artifacts-ready":
                raise ValueError(original.diagnostic)
            jars = [prep / p for p in original.classpath]
            classes = work / "classes"
            classes.mkdir()
            cp = os.pathsep.join(map(str, [classes,*jars]))
            source = HERE / "RegistrationTrace.java"
            subprocess.run([jdk/"bin/javac","--release","21","-parameters","-proc:none","-d",classes,"-cp",cp,source],check=True)
            who = original.source["target"]
            report = {"scope":"historical registrar and observing registry", "commit":original.commit, "side":side,
                      "target":who, "runtimeJars":[digest(j) for j in jars], "jdk":runtime_jdk.release(jdk),
                      "sourceSha256":digest(source),"observerClass":digest(classes/"springwork/RegistrationTrace.class")}
            physical = invocation([jdk/"bin/java","-cp",cp,"springwork.RegistrationTrace"],"jvm",dest,work,env)
            sequence = 978 if side=="parent" else 789
            if physical["exit"] or (dest/physical["stdout"]).read_text().splitlines() != ["9", str(sequence)]:
                raise ValueError("unexpected public registration callbacks")
            report["jvm"] = physical
            report["sequence"] = [9,sequence]
            if not physical_only:
                checker = Path(os.environ["JVMCONTRACT"])
                expected = [("springwork.RegistrationTrace", "sequence", "(I)I", classes, report["observerClass"]),
                            (who["class"], who["method"], who["descriptor"], prep/who["loadedFrom"], who["classSha256"])]
                request = {"classpath": [str(p) for p in [classes,*jars]],
                           "classes": [{"class": cls, "method": method, "descriptor": desc} for cls,method,desc,_,_ in expected]}
                answer, release = class_binding.ask(checker, env, work, {side:request})
                for binding, (cls, _, _, provider, actual) in zip(answer[side]["bindings"], expected, strict=True):
                    mismatch = class_binding.disagreement(cls, binding, str(provider), actual)
                    if mismatch: raise ValueError(mismatch)
                report.update(checkerSha256=digest(checker), source=os.environ.get("VERIFY_SOURCE_COMMIT"),
                              nativeClassBindings={name:actual for name,_,_,_,actual in expected}, boundRelease=release, queries={})
                for label,roots in ([("recorded",ROOTS)] if probe else [("ordinary",[]),("recorded",ROOTS)]):
                    result = proof(checker,classes,jars,work,env,dest,METHOD,label,GUARD,
                                   f"(code == 0 && result == 9) || (code == 1 && result == {sequence})",
                                   roots,(256,16384),PROFILE)
                    report["queries"][label]=result
                    print(side,label,result["verdict"],result.get("blocker"),flush=True)
            write(dest/"measurement.json",report)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-only", action="store_true")
    parser.add_argument("--probe", action="store_true", help="one recorded-startup parent claim for a capped diagnostic")
    args = parser.parse_args()
    run(args.output, physical_only=args.physical_only, probe=args.probe)
