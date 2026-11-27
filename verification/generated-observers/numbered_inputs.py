"""Exercise literal coverage, predicate order and review stops through ordinary numbered setup."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import campaign
import numbered_handoff
import scaffold_example
from targets import observer_recipes, observer_review


def question(name, history, expected):
    return {"id": name, "role": "Control", "args": [name], "history": history,
            "prediction": "Each original release supplies the registered finite observation.",
            "basis": "Review of the specified input and public operation.",
            "refutation": "A different type, value, exception or callback count refutes this prediction.",
            "expected": {s: {"return": expected} for s in ("parent", "fix")}}


def run(root):
    numeric = question("numbered.format-and-malformed",
                       "Parse `1,5` and `oops` as BigDecimal using the registered NumberFormat.",
                       "BigDecimal=1.5 IllegalArgumentException")
    fmt = {"locale": "de-DE", "pattern": "0.0", "parseBigDecimal": False}
    ordered = question("numbered.selection-order",
                       "Use [1,2,3] twice, first selecting odd values, then selecting values >5.",
                       "true/3/0,false/99/1")
    cases = {"458": {"inputDefaults": {"numberFormat": fmt}, "questions": [numeric]},
             "445": {"inputDefaults": {"fallback": 99}, "questions": [ordered]}}
    workspace = root / "numbered"
    workspace.mkdir()
    numbered_handoff.handoff(workspace, list(cases), reviewed=cases,
                             archive=campaign.HERE/"receipts/numbered-inputs.zip")
    spring = next((workspace/"examples").glob("458-*"))
    reg = campaign.read(spring/"records/public-observer/registration.json")
    actual = reg["questions"][0]["inputs"][0]["conversions"]
    if (not reg["entry"].endswith(observer_recipes.FORMATTED_NUMBER_ENTRY) or
            actual != [{"text": t, "type": "BigDecimal", "format": fmt} for t in ("1,5", "oops")]):
        raise ValueError("numbered setup lost the formatted overload, literal, or target class")

    limit = root / "open"
    limit.mkdir()
    folder = limit / "examples" / spring.name
    folder.mkdir(parents=True)
    for filename in ("example.json", "runtime.json", "comparison.json"):
        shutil.copyfile(spring / filename, folder / filename)
    inputs = campaign.read(folder/"comparison.json")
    plan = campaign.read(workspace/"plan.json")
    setup = plan["examples"][0]["publicComparison"]
    stops = {}
    for name in ("formatter-unspecified", "unregistered-rounding-mode"):
        if name == "formatter-unspecified":
            setup["inputDefaults"] = {}
            wanted = "which NumberFormat"
        else:
            setup["inputDefaults"] = {"numberFormat": fmt}
            q = question("numbered.rounding-mode",
                         "Parse `1,5` as BigDecimal using the registered NumberFormat, then read `getRoundingMode()` from that formatter.",
                         "BigDecimal=1.5 roundingMode=HALF_EVEN")
            inputs["questions"] = [q]
            wanted = "getRoundingMode()"
        campaign.write(folder/"comparison.json", inputs)
        campaign.write(limit/"plan.json", plan)
        result = scaffold_example.scaffold("458", limit/"plan.json", True, root=limit)
        review = campaign.read(folder/"records/reviewed-public-inputs/review.json")
        if (review["status"] != "open" or wanted not in review["firstOpenDependency"]
                or review["firstOpenDependency"] not in result["leftForSetup"]
                or (folder/"records/public-observer").exists() or (folder/"records/entry-bindings.json").exists()):
            raise ValueError("setup accepted a partial history or lost its first missing operation")
        stops[name] = {"questions": inputs["questions"], "inputDefaults": setup["inputDefaults"], "review": review}
    jdk = campaign.JDKS / campaign.read(folder/"runtime.json")["jdk"]
    getters = subprocess.check_output([jdk/"bin/javap", "-public", "-s", "java.text.DecimalFormat"], text=True)
    if "public java.math.RoundingMode getRoundingMode();" not in getters:
        raise ValueError("the registered read is absent from the pinned formatter API")
    record = campaign.read(spring/"records/public-observer/generation.json")
    stops["unregistered-rounding-mode"].update(entry=reg["entry"], declarations=record["declarations"],
        read="java.text.DecimalFormat#getRoundingMode()Ljava/math/RoundingMode;", jdkReleaseSha256=record["jdkReleaseSha256"])
    def must_reject(reason):
        try:
            observer_review.saved_setup(spring)
        except ValueError as error:
            if reason not in str(error):
                raise
            return str(error)
        raise ValueError("a changed numbered review resumed the old caller")

    predicates = spring/"records/reviewed-public-inputs/predictions.json"
    saved = predicates.read_bytes()
    different = campaign.read(predicates)
    different[numeric["id"]]["new"][0][0][2] = "1.4"
    campaign.write(predicates, different)
    stops["changed-predicate-file"] = must_reject("predictions differ")
    predicates.write_bytes(saved)
    observer_review.saved_setup(spring)
    retry = campaign.read(workspace/"plan.json")
    retry["examples"][0]["publicComparison"]["inputDefaults"]["numberFormat"]["parseBigDecimal"] = True
    retry_path = workspace/"retry.json"
    campaign.write(retry_path, retry)
    result = scaffold_example.scaffold("458", retry_path, True, root=workspace)
    refusal = must_reject("a different reviewed experiment needs a new scaffold")
    if result["refused"] != [refusal] or campaign.read(spring/"records/public-observer/generation.json") != record:
        raise ValueError("a refused fixture change altered the saved caller")
    stops["changed-formatter-retry"] = refusal
    campaign.write(limit/"first-stops.json", stops)
    campaign.pack(limit, [limit/"first-stops.json", limit/"plan.json", folder/"comparison.json", folder/"runtime.json",
                          folder/"records"], campaign.HERE/"receipts/numbered-input-stops.zip")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="numbered-input-review-") as tmp:
        run(Path(tmp))
