"""Reproduce example 333's actual context restoration and both public resource readbacks."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "lib/benchmark/classpath-entry-discovery"))
import original_controls as controls
from targets import blind_measure, change_evidence, deployment_graph, public_observation, upgrade_replay


def run(work):
    rows = controls.loaders(work)
    historical = json.loads((ROOT / "verification/classpath-entry-discovery/loaders.json").read_bytes())
    witnesses = []
    jdk = Path(controls.JDK)
    restore = HERE / "loader/ContextRestoration.java"
    observer = HERE / "loader/ResourceChoices.java"
    compiled = work / "observer-classes"
    compiled.mkdir()
    subprocess.run([jdk / "bin/javac", "-proc:none", "-cp", work/"default.jar", "-d", compiled, restore], check=True)
    for row in rows[:3]:
        side = row["revision"]
        prior = next(r for r in historical if r.get("revision") == side)
        if row["observations"] != prior["observations"] or row["originalHistories"] != 16:
            raise ValueError("the 16 original loader histories changed")
        answer = controls.java([compiled,work/(side+".jar")], "trial.ContextRestoration")
        if answer != "16 normal returns and 1 ArrayIndexOutOfBoundsException restored the same loader":
            raise ValueError("no original readback of the exact outer context")
        refusal, = row["nativeBinding"].values()
        if refusal["status"] != "open" or "delegation" not in str(refusal["firstOpenDependency"]):
            raise ValueError("the native custom-loader guard was lost")
        witnesses.append({"revision":side,"restoration":answer,"originalJar":upgrade_replay.sha(work/(side+".jar")),
                          "originalHistories":row["observations"],"native":refusal})
    scoped = work / "compensating"
    subprocess.run([jdk/"bin/javac", "-proc:none", "-cp", scoped/"old/classes", "-d", compiled, observer], check=True)
    raw = {}
    for side in ("old", "new"):
        directory = scoped / side
        resource, = directory.glob("*.jar")
        runs = []
        for _ in range(2):
            result = controls.java([compiled,directory/"classes",resource], "ResourceChoices")
            observed = {}
            for line in result.splitlines():
                name, url, first_byte, returned = line.split("\t")
                observed[name] = {"firstByte":int(first_byte),"returned":int(returned),"url":url}
            runs.append(observed)
        if runs[0] != runs[1] or runs[0]["META-INF/missing"] != {"firstByte":-1, "returned":-1, "url":"absent"}:
            raise ValueError("fresh original loader calls disagree")
        actual = runs[0]["META-INF/paint"]
        if (actual["firstByte"],actual["returned"]) != (65 if side == "old" else 66,65):
            raise ValueError("original byte and public compensated value no longer match the two hypotheses")
        if not actual["url"].endswith(resource.name + "!/META-INF/paint"):
            raise ValueError("the actual loader selected another provider")
        raw[side] = {"runs":runs, "resourceSha256":upgrade_replay.sha(resource),
                     "classSha256":upgrade_replay.sha(directory/"classes/PairResourceGate.class")}
    choices = []
    for entry, field in (("ClassLoader.getResources → InputStream.read","firstByte"),("PairResourceGate.read","returned")):
        values = {side:[r["META-INF/paint"][field] for r in evidence["runs"]] for side, evidence in raw.items()}
        choices.append({"entry":entry, "history":[entry], "observationFields":[field],
                        "originalObservations":values, "disposition":"established" if field=="firstByte" else "preserved",
                        "evidence":{"observerSource":upgrade_replay.sha(observer), "callerBytecode":upgrade_replay.sha(compiled/"ResourceChoices.class")}})
    decision = public_observation.intent_decision(choices)
    if not decision or not all(c["entry"] in decision for c in choices):
        raise ValueError("the watcher omitted an independently measured alternative")
    incomplete = {**choices[0], "entry":"unmeasured alternative", "requiredSides":["old","new"],
                  "originalObservations":{"old":[65],"new":[]}}
    if public_observation.intent_decision([choices[0], incomplete]) is not None:
        raise ValueError("a readback missing its required side was offered as a qualified alternative")
    packet = work / "packet"
    packet.mkdir()
    url = "https://github.com/example/loader-choice/pull/1"
    sample = {"layoutKnown":False, "loader":{"scope":"context children","delegation":"custom"}, "classpath":[]}
    change_evidence.write_json(packet/"packet.json", {"url":url, "old":sample, "new":sample})
    missing = public_observation.watch(url,packet,work/"review",True)
    if missing["stoppedAt"] != "original loader binding" or "loader URL" not in missing["ownerDecision"]:
        raise ValueError("owner did not receive the missing physical URL-to-artifact question")
    original = {"file":"default.jar","sha256":upgrade_replay.sha(work/"default.jar")}
    physical = {**sample, "classpath":[original], "revision":"original-333"}
    manifests = blind_measure.original_manifests(work,{},{"old":physical,"new":physical},work/"manifests",upgrade_replay.sha(jdk/"release"))
    if any(json.loads(path.read_bytes())["loader"]!=physical["loader"] for path in manifests.values()):
        raise ValueError("neutral packet dropped a declared nonstandard loader")
    captured = work / "captured/lib/default.jar"
    captured.parent.mkdir(parents=True)
    shutil.copyfile(work/"default.jar",captured)
    mapped = {**physical, "layoutKnown":True, "deploymentRoot":"captured",
              "classpath":[{**original, "deploymentPath":"/lib/default.jar"}]}
    if "defining loader" not in deployment_graph.loader_decision(mapped):
        raise ValueError("supplying a physical map concealed the unknown native delegation rule")
    blind_measure.pinned_artifacts(work, mapped, "classpath")
    captured.write_bytes(b"changed captured fixture")
    try:
        blind_measure.pinned_artifacts(work, mapped, "classpath")
    except ValueError as error:
        if "captured deployment artifact changed" not in str(error):
            raise
        changed_copy = str(error)
    else:
        raise ValueError("a previous loader map accepted changed original bytes")
    answer = {"changedMappedArtifact":changed_copy,"scope":"original context-loader example and two readbacks on one compensating release pair",
              "jdkReleaseSha256":upgrade_replay.sha(jdk/"release"),"threeRevisions":witnesses,
              "historicalResourceProfiles":rows[3:], "sameDeploymentReadbacks":raw,
              "observerClassSha256":upgrade_replay.sha(compiled/"ResourceChoices.class"),
              "restorationClassSha256":upgrade_replay.sha(compiled/"trial/ContextRestoration.class"),
              "choices":choices,"ownerDecision":decision,"missingMapping":missing}
    with zipfile.ZipFile(HERE/"loader-choices.zip","w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("qualification.json",json.dumps(answer,indent=2)+"\n")
        for file in (restore, observer, compiled/"ResourceChoices.class", compiled/"trial/ContextRestoration.class"):
            archive.write(file,file.name)
    print("48 original two-call histories, 3 abrupt restorations, 2 distinct qualified public observations")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="original-loader-decisions-") as scratch:
        run(Path(scratch))
