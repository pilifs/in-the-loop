"""Qualify the retained public argument through numbered setup, resume and two planted callers."""
import base64
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "generated-observers"))
import campaign
import falsifiers
import numbered_handoff
import numbered_inputs
from targets import observer_generation, upgrade_replay


def qualify(root, flag):
    word = str(flag).lower()
    question = numbered_inputs.question(
        "formatter.after-return", "Parse `1,5` as BigDecimal using the registered NumberFormat, "
        "then read `isParseBigDecimal()` from that formatter.", "BigDecimal=1.5 parseBigDecimal=" + word)
    fixture = {"pattern": "0.0", "locale": "de-DE", "parseBigDecimal": flag}
    reviewed = {"458": {"questions": [question], "inputDefaults": {"numberFormat": fixture}}}
    checkout = root / ("numbered-" + word)
    checkout.mkdir()
    numbered_handoff.handoff(checkout, ["458"], reviewed=reviewed, archive=root / ("numbered-" + word + ".zip"))
    folder, = (checkout / "examples").glob("458-*")
    bundle = folder / "records/public-observer"
    source = (bundle / "UpgradeProbe.java").read_text()
    getter = "((java.text.DecimalFormat)format).isParseBigDecimal()"
    setup = "java.text.NumberFormat format = numberFormat((Map<String,Object>)pair.get(\"format\"));"
    if source.count(getter) != 1 or source.count(setup) != 1:
        raise ValueError("planted control could not locate the generated call site")
    other = "((java.text.DecimalFormat)numberFormat((Map<String,Object>)pair.get(\"format\"))).isParseBigDecimal()"
    sources = {"original": source, "different-formatter": source.replace(getter, other),
               "premature-getter": source.replace(getter, "earlyValue").replace(setup, setup + "\n            boolean earlyValue = " + getter + ";")}
    q, = campaign.read(bundle / "registration.json")["questions"]
    jdk = campaign.JDKS / campaign.read(folder / "runtime.json")["jdk"]
    encoded = [base64.b64encode(arg.encode("utf-16-be")).decode() for arg in observer_generation.arguments(q["inputs"][0])]
    result = {}
    for side in ("old", "new"):
        manifest = campaign.read(bundle / (side + ".json"))
        rows = {}
        for name, candidate in sources.items():
            trial = root / (word + "-" + side + "-" + name)
            row = falsifiers.dynamic(bundle, jdk, trial, candidate, q, 0, side)
            plain = trial / "plain.txt"
            cp = os.pathsep.join([str(trial), *(r["file"] for r in manifest["classpath"])])
            subprocess.run([jdk / "bin/java", "-Dupgrade.observation.file=" + str(plain), "-cp", cp,
                            "UpgradeObservation", "UpgradeProbe", *encoded], check=True, timeout=20)
            row["plain"] = upgrade_replay.typed_outcome(plain.read_text().splitlines())
            if row["raw"] != row["plain"] or row["raw"] != observer_generation.wire([["return", "java.math.BigDecimal", "1.5", flag]]):
                raise ValueError("original JVM output differs for " + name)
            if name == "original":
                read, = row["projection"]["argumentReads"]
                if read["value"] is not flag or not read["afterNormalReturn"]:
                    raise ValueError("the normal return lost its original argument read")
            elif "refusal" not in row:
                raise ValueError("false qualification for " + name)
            rows[name] = row
        result[side] = {"revision": manifest["commit"], "classpath": manifest["classpath"], "attempts": rows}
    return result


def main():
    with tempfile.TemporaryDirectory(prefix="retained-formatter-") as scratch:
        root = Path(scratch)
        results = {str(flag).lower(): qualify(root, flag) for flag in (False, True)}
        campaign.write(root / "qualification.json", results)
        campaign.pack(root, [root / "qualification.json", *root.glob("numbered-*.zip")], HERE / "formatter.zip")
    print("Two original releases, two initial flags, four genuine readbacks and eight independently rejected planted callers")


if __name__ == "__main__":
    main()
