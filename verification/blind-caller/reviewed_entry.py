"""Exercise supplied, unchanged public owners through sealed prediction, normal review and original JVM replay."""
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

from product_controls import HERE, packet, read
from targets import blind_prediction, change_evidence, observer_scalar, public_observation, runtime_jdk, upgrade_replay


def run(work):
    data = work / "packet"
    jdk = Path(runtime_jdk.home(17))
    metadata = packet(data, jdk)
    for side in ("old", "new"):
        original = data / side / "subject.jar"
        java = data / side / "StableApi.java"
        java.write_text("package trial; public class StableApi { public static int count(int n) { return n; } }")
        subprocess.run([jdk/"bin/javac","-g","-proc:none","-d",java.parent,java], check=True)
        with zipfile.ZipFile(original, "a") as archive:
            archive.write(java.parent/"trial/StableApi.class","trial/StableApi.class")
        metadata[side]["classpath"][0]["sha256"] = upgrade_replay.sha(original)
    metadata["arm"] = "reviewed"
    target = "trial.StableApi#count(I)I"
    metadata["reviewed"] = {
        "entry":target, "history":"Call the stable public count with seven on each original API.",
        "fields":observer_scalar.FIELDS, "inputs":[{"arguments":[7]}],
        "prediction":{"relation":"equal on all registered inputs"}, "requiredSides":["old","new"]}
    change_evidence.write_json(data/"packet.json",metadata)
    location = work/"verified"
    result = public_observation.watch(metadata["url"],data,location,execute=True)
    primary = result["candidates"][result["primary"]]
    if (primary["entry"] != target or primary["disposition"] != "established" or
            not all(primary["originalObservations"][side] for side in ("old","new"))):
        raise ValueError("the supplied unchanged owner and its original readbacks were not qualified")
    for rows in primary["originalObservations"].values():
        if [json.loads(r["return"]) for r in rows] != [[["return","java.lang.Integer","7"]]]:
            raise ValueError("the reviewed public call has a different original outcome")
    metadata["reviewed"]["entry"] = "trial.Unavailable#count(I)I"
    change_evidence.write_json(data/"packet.json",metadata)
    absent = blind_prediction.derive(data,metadata)
    if absent["candidates"] or absent["primary"] is not None or metadata["reviewed"]["entry"] not in absent["firstOpenDependency"]:
        raise ValueError("a missing exact reviewed declaration was replaced by a different public method")
    change_evidence.write_json(work/"absent.json",absent)
    with zipfile.ZipFile(HERE/"reviewed-entry.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for p in [work/"absent.json", location/"review.json",location/"prediction/prediction.json",
                  *location.glob("measured/**/receipts/*.json"), *location.glob("measured/**/bundle/caller.zip"),
                  *location.glob("measured/**/bundle/UpgradeProbe.java")]:
            archive.write(p,p.relative_to(work))
    print("Reviewed owner outside the production diff measured on both originals; missing descriptor returned to owner")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="reviewed-original-declaration-") as tmp:
        run(Path(tmp))
