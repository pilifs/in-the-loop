"""Check the 21 saved Java-semantics launch graphs through the current product binding path."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from transfer import ROOT, JDK
from targets import change_evidence, change_inventory, entry_binding, upgrade_replay

sys.path.insert(0, str(ROOT / "lib/benchmark/java-semantics-gap"))
from campaign import CACHE, CLAIMS, compile_java, javaenv


def run(destination):
    source = ROOT / "verification/java-semantics-gap/heap-and-gson/origins.json"
    expected = json.loads(source.read_bytes())["graphs"]
    graphs, asked = {}, {}
    image = change_inventory.jdk_binding(JDK)
    with tempfile.TemporaryDirectory(prefix="historical-bindings-") as tmp:
        work = Path(tmp)
        for name, reference in expected.items():
            subject = CLAIMS[name]
            sources = list((ROOT / "examples").glob(f"{subject.example}-*/adapter/**/{subject.owner}.java"))
            if len(sources) != 1 or upgrade_replay.sha(JDK / "lib/modules") != reference["jdkSha256"]:
                raise ValueError(f"{name}: historical source or JDK identity differs")
            libraries = [CACHE / row["path"] for row in reference["classpath"][1:]]
            if any(upgrade_replay.sha(file) != row["sha256"] for file,row in zip(libraries,reference["classpath"][1:],strict=True)):
                raise ValueError(f"{name}: original library bytes differ")
            classes = work / name
            compile_java(sources, classes, libraries, javaenv())
            files = [classes, *libraries]
            launch = {"kind": "historical application", "commit": reference["source"], "jdk": image,
                      "classpath": [{"file": str(f), "sha256": change_inventory.file_digest(f)} for f in files]}
            launch["key"] = change_inventory.digest(launch)
            graphs[name] = files, launch, JDK
            asked[name] = sorted(reference["classes"])
        checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"))
        records = entry_binding.qualify(checker, graphs, asked)
        rows = []
        for name, bindings in records.items():
            for cls, record in bindings.items():
                wanted = expected[name]["classes"][cls]
                actual = {"provider": record.get("providerIndex"), "entry": record.get("physicalEntry"),
                          "sha256": record.get("classSha256")}
                rows.append({"graph": name, "class": cls, "expected": wanted, "actual": actual,
                             "jvmLoader": record["jvm"]["definingLoader"], "agreement": actual == wanted,
                             "firstOpenDependency": record.get("firstOpenDependency")})
        result = {"case": 12, "sourceSha256": upgrade_replay.sha(source), "engine": "native class-bindings",
                  "stockJbmcQualification": "unmeasured", "graphs": len(graphs), "bindings": rows,
                  "matched": sum(r["agreement"] for r in rows), "jdkImage": image}
        change_evidence.write_json(destination, result)
        if (len(graphs), len(rows), result["matched"]) != (21, 283, 283):
            raise ValueError(f"{result['matched']}/{len(rows)} measured origins reproduced")
        print("21 graphs and 283 physical origins matched the native resolver and the fresh JVMs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
