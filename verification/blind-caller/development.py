"""Compare the three disclosed public histories with their archived originals and challenged callers."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "generated-observers"))
import campaign
import falsifiers
from targets import observer_generation


def replace(source, before, after):
    if before not in source:
        raise ValueError("planted caller missed its intended source instruction: " + before)
    return source.replace(before, after)


def plants(case, source, recipe):
    if case == "484":
        owner, getter = recipe["owner"], recipe["getter"]
        read = "millis(copy." + getter + "())"
        return {"reconstructed-copy": replace(source, read, "millis(new " + owner + "(message)." + getter + "())"),
                "same-handle": replace(source, read, "millis(message." + getter + "())")}
    if case == "466":
        return {"unsubscribed": replace(source, ".blockLast(java.time.Duration.ofSeconds(10))", ""),
                "inner-only": replace(source, "terminal[1]=error.getClass().getName()",
                                      "terminal[1]=error.getCause()==null ? null : error.getCause().getClass().getName()")}
    reader, writer, cfg, directory = (recipe["types"][k] for k in ("DirectoryReader", "IndexWriter", "IndexWriterConfig", "ByteBuffersDirectory"))
    fresh = "private static " + directory + " emptyIndex() throws IOException { " + directory + " d = new " + directory + "(); try (" + writer + " w = new " + writer + "(d, new " + cfg + "())) {} return d; }\n"
    different = replace(source, reader + ".open(directory)", reader + ".open(emptyIndex())")
    different = replace(different, "private static List<Object> hits(", fresh + "private static List<Object> hits(")
    return {"fresh-index": different, "count-only": replace(source, "doc : found.scoreDocs", "doc : new org.apache.lucene.search.ScoreDoc[0]")}


def qualify(case, work):
    jdk = campaign.prepare(case, work)
    reg = campaign.HERE / "registrations" / (case + ".json")
    predictions = campaign.HERE / "predictions" / (case + ".json")
    bundle = work / "bundle"
    generation = observer_generation.materialize(reg, predictions, work/"old.json", work/"new.json", jdk, bundle)
    if generation["status"] != "compiled":
        raise ValueError(generation["firstOpenDependency"])
    plan = work / "application.json"
    campaign.run([sys.executable, campaign.ROOT / "examples/tools/build.py", "--change-plan", "application",
                  "--before", bundle/"old.json", "--after", bundle/"new.json", "--jdk", jdk, "--supplied-only",
                  "--workflows", bundle/"workflows.json", "--run", "--seconds", "240", "--output", plan])
    report = campaign.read(plan)
    with zipfile.ZipFile(campaign.HERE / "receipts" / (case + "-clean.zip")) as archive:
        historical = {n["id"]:n for n in json.loads(archive.read("cold.json"))["claims"]}
    for node in report["claims"]:
        ref = historical.pop(node["id"])
        if node["status"] != ref["status"] or not node.get("children"):
            raise ValueError(f"{node['id']}: {node.get('firstOpenDependency')} {node.get('reason')}")
        for a,b in zip(node["children"],ref["children"],strict=True):
            if any(a.get(side) != b.get(side) for side in ("old","new")):
                raise ValueError("original side observation changed")
        evidence = campaign.read(work/node["receipt"]["path"])
        for side in evidence["sides"].values():
            for trial in side["trials"]:
                first, second = trial["publicProjections"]
                if not first.get("actionBindings") or first != second:
                    raise ValueError("the independent readback or its original bindings did not repeat")
    if historical:
        raise ValueError("a registered history was omitted")
    source = (bundle/"UpgradeProbe.java").read_text()
    question = campaign.read(reg)["questions"][0]
    controls = {}
    for name, candidate in plants(case, source, generation["recipe"]).items():
        controls[name] = {}
        for side in ("old", "new"):
            result = falsifiers.dynamic(bundle, jdk, work/(name+"-"+side), candidate, question, 0, side)
            if "refusal" not in result:
                raise ValueError("planted " + name + " qualified on " + side)
            controls[name][side] = result
    campaign.write(work/"controls.json", controls)
    receipts = [work/node["receipt"]["path"] for node in report["claims"]]
    campaign.pack(work, [plan, work/"controls.json", bundle, *receipts], HERE/(case+"-development.zip"))
    print(case, {n["id"]:n["status"] for n in report["claims"]}, "four planted callers refused")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("J14","466","484"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="public-actions-") as scratch:
        qualify(args.case, Path(scratch))
