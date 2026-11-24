"""Make a local manifest resource appear, bind it explicitly, and compare resumed and empty-cache application plans."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from scaffold_first import DEST, JDK, compile_java, digest, javaenv, read, save, scratch
from history import ROOT


def main(alternate_case=False):
    manifest_name = "meta-inf/manifest.mf" if alternate_case else "META-INF/MANIFEST.MF"
    out = DEST / ("manifest-case-controls" if alternate_case else "manifest-controls")
    out.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    with scratch(prefix="manifest-presence-") as tmp:
        work = Path(tmp)
        src = work / "Palette.java"
        src.write_text("""package demo;
public class Palette {
    public static int read() throws java.io.IOException {
        try (java.io.InputStream in = Palette.class.getResourceAsStream("palette.txt")) {
            return in == null ? 0 : in.read();
        }
    }
}""")
        compiled = work / "compiled"
        compile_java([src], compiled, [], javaenv())
        manifests = {}
        for side in ("old", "new"):
            folder = work / side
            folder.mkdir()
            jar = folder / "palette.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(manifest_name, "Manifest-Version: 1.0\r\nClass-Path: optional.jar\r\n\r\n")
                archive.write(compiled / "demo/Palette.class", "demo/Palette.class")
            manifests[side] = {"sourceSha256": digest(src), "commit": "constructed-" + side,
                               "classpath": [{"file": str(jar), "sha256": digest(jar)}]}
            save(work / (side + ".json"), manifests[side])
        probe = work / "UpgradeProbe.java"
        probe.write_text("""public class UpgradeProbe {
            public static String observe(String[] args) throws Exception { return Integer.toString(demo.Palette.read()); }
        }""")
        scope = {"entry": "demo.Palette#read()I", "probeClass": "UpgradeProbe",
                 "observer": "First resource byte or zero for absence",
                 "basis": "A one-byte optional resource on only the new deployment",
                 "cases": [{"args": [], "expected": {"return": "0"}}]}
        save(work / "scope.json", scope)
        workflow = {"id": "resource", "scope": "scope.json", "probe": "UpgradeProbe.java", "cohort": "registered",
                    "intent": "preserve", "deterministicUnderAssumptions": True,
                    "assumptions": ["The two local deployments remain stable over each pair of original JVM trials."]}
        save(work / "workflows.json", {"schema": "caller-workflows/v1", "change": "manifest resource presence", "workflows": [workflow]})
        records = {}
        optional = work / "new/optional.jar"
        previous = None
        with zipfile.ZipFile(out / "plans.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            saved = set()
            for name, expected in (("absent", "established"), ("repeat", "established"), ("appeared", "open"),
                                   ("bound", "refuted"), ("bound-clean", "refuted"), ("restored", "established")):
                if name == "appeared":
                    with zipfile.ZipFile(optional, "w") as resource:
                        resource.writestr("demo/palette.txt", "R")
                if name == "bound":
                    manifests["new"]["classpath"].append({"file": str(optional), "sha256": digest(optional)})
                    save(work / "new.json", manifests["new"])
                if name == "restored":
                    optional.unlink()
                    manifests["new"]["classpath"].pop()
                    save(work / "new.json", manifests["new"])
                plan = work / (name + ".json")
                cmd = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application", "--run",
                       "--before", work / "old.json", "--after", work / "new.json", "--jdk", JDK, "--checker", checker,
                       "--workflows", work / "workflows.json", "--output", plan, "--cache", work / ("clean" if name == "bound-clean" else "cache")]
                if previous is not None:
                    cmd += ["--previous", previous]
                subprocess.run(cmd, check=True, cwd=ROOT)
                full = read(plan)
                claim, = full["claims"]
                observed = claim["children"][0]
                actions = {s: val["action"] for s, val in claim["execution"].items()}
                new_value = "82" if name in ("appeared", "bound", "bound-clean") else "0"
                if (claim["status"] != expected or observed["old"] != {"return": "0"} or observed["new"] != {"return": new_value}
                        or (name in ("repeat", "restored") and actions != {"old": "exact reuse", "new": "exact reuse"})
                        or (name in ("appeared", "bound", "bound-clean") and actions["new"] == "exact reuse")):
                    raise ValueError(f"{name}: unexpected manifest evidence or reuse: {claim}")
                records[name] = {"status": expected, "newReturn": new_value, "execution": actions,
                                 "open": claim.get("firstOpenDependency"), "newManifest": full["launches"]["new"]["production"]["manifestClassPath"]}
                archive.write(plan, plan.name)
                for item in sorted((work / "receipts").glob("*.json")):
                    if item.name not in saved:
                        archive.write(item, "receipts/" + item.name)
                        saved.add(item.name)
                previous = plan
                print(name, expected, new_value, actions, flush=True)
        save(out / "summary.json", {"job": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
             "checkerSha256": digest(checker), "manifestMember": manifest_name, "archiveSha256": digest(out / "plans.zip"), "observations": records})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--alternate-case", action="store_true")
    main(p.parse_args().alternate_case)
