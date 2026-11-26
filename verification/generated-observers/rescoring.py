"""Re-score two historical baseline discrepancies and challenge reuse of their JVM receipts offline."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import zipfile

import campaign
from targets import observer_rescore, upgrade_replay


def evaluate(case, root):
    archive = campaign.HERE / "receipts" / (case + "-clean.zip")
    with zipfile.ZipFile(archive) as saved:
        for name in saved.namelist():
            if name == "cold.json" or name.startswith(("bundle/", "receipts/")):
                saved.extract(name, root)
    bundle, report = root / "bundle", root / "cold.json"
    plan = campaign.read(report)
    predictions = campaign.read(campaign.HERE / "predictions" / (case + ".json"))
    question = "earlier-change" if case == "06" else "spring-projects/spring-framework#37193.1"
    node = next(n for n in plan["claims"] if n["id"] == question)
    if node["status"] != "open":
        raise ValueError("the original incorrect baseline must stay in the historical denominator")

    def score(values, source=report):
        path = root / "new-predictions.json"
        campaign.write(path, values)
        rescored = observer_rescore.score(source, bundle, path)
        return next(c for c in rescored["claims"] if c["id"] == question)

    original = score(predictions)
    corrected = copy.deepcopy(predictions)
    if case == "06":
        corrected[question]["old"] = predictions["viewport"]["old"]
    else:
        corrected[question]["old"] = [[[[], "error",
            "org.springframework.web.reactive.function.client.WebClientResponseException", "java.lang.NumberFormatException"]]]
    agreed = score(corrected)
    wrong = copy.deepcopy(corrected)
    if case == "06":
        wrong[question]["new"][0][0][1] = 5
    else:
        wrong[question]["new"][0][0][0].reverse()
    refuted = score(wrong)
    attempts = {"registered": original, "correctedParent": agreed, "wrongFix": refuted}
    if ([r["status"] for r in attempts.values()] != ["open", "established", "refuted"]
            or any(r["receipt"] != node["receipt"] or r["originalStatus"] != "open" for r in attempts.values())
            or len({r["observationsSha256"] for r in attempts.values()}) != 1):
        raise ValueError("only the evaluator should change between the three adjudications")

    controls = {}
    alternative = root / "diagnostic-plan.json"
    original_node = copy.deepcopy(node)
    for label, changes in (("unclosedDeployment", {"rescoreDomainClosed": False}),
                           ("startupStop", {"firstOpenDependency": "startup before the public entry"})):
        node.update(changes)
        campaign.write(alternative, plan)
        result = score(corrected, alternative)
        if result["status"] != "open" or "observationsSha256" in result:
            raise ValueError("an open deployment or startup failure was re-scored")
        controls[label] = result["firstOpenDependency"]
        node.clear()
        node.update(original_node)

    def revised_receipt(evidence):
        path = root / "receipts" / "diagnostic.json"
        campaign.write(path, evidence)
        ref = {"path": "receipts/diagnostic.json", "sha256": upgrade_replay.sha(path)}
        node["receipt"] = ref
        for witnesses in plan["bindingWitnesses"].values():
            for witness in witnesses:
                if witness["claim"] == question:
                    witness["receipt"] = ref
        campaign.write(alternative, plan)

    receipt = campaign.read(root / original_node["receipt"]["path"])
    partial = copy.deepcopy(receipt)
    partial["sides"]["old"]["trials"][0]["publicProjections"].pop()
    revised_receipt(partial)
    incomplete = score(corrected, alternative)
    if incomplete["status"] != "open" or "observationsSha256" in incomplete:
        raise ValueError("a missing original repetition was promoted")
    controls["missingRepeatedProjection"] = "open"

    def refused(label, reason, source):
        try:
            score(corrected, source)
        except ValueError as error:
            if reason not in str(error):
                raise
            controls[label] = str(error)
        else:
            raise ValueError("re-scoring accepted " + label)

    switched = copy.deepcopy(receipt)
    switched["sides"]["old"]["entryBinding"] = receipt["sides"]["new"]["entryBinding"]
    revised_receipt(switched)
    refused("crossedDeployment", "bound deployment", alternative)
    reg = campaign.read(bundle / "registration.json")
    reg["questions"][0]["history"] += " (different review)"
    campaign.write(bundle / "registration.json", reg)
    refused("changedRegistration", "registration", report)
    return {"archive": "receipts/" + archive.name, "archiveSha256": upgrade_replay.sha(archive),
            "reportSha256": upgrade_replay.sha(report), "question": question,
            "predicates": {k: v[question] for k, v in zip(attempts, (predictions, corrected, wrong))},
            "adjudications": attempts, "controls": controls}


def live(work):
    """Begin with one wrong parent predicate, so no sibling claim can establish runtime stability."""
    from controls import app
    from targets import observer_generation
    name = "formatted-number"
    jdk = campaign.prepare("458-format", work)
    source = campaign.read(campaign.HERE / "registrations/458-format.json")
    reg = work / "registration.json"
    campaign.write(reg, {**source, "questions": [q for q in source["questions"] if q["id"] == name]})
    expected = campaign.read(campaign.HERE / "predictions/458-format.json")[name]
    wrong = copy.deepcopy(expected)
    wrong["old"][0][0][2] = "1.4"
    before, after = work / "wrong-parent.json", work / "corrected-parent.json"
    campaign.write(before, {name: wrong})
    campaign.write(after, {name: expected})
    bundle = work / "bundle"
    campaign.isolated(reg, work, jdk, bundle)
    observer_generation.materialize(reg, before, work/"old.json", work/"new.json", jdk, bundle)
    report = work / "original.json"
    node, = app(work, bundle, jdk, bundle/"workflows.json", report)["claims"]
    if node["status"] != "open" or node.get("rescoreDomainClosed") is not True:
        raise ValueError("expected a wrong baseline measured on a closed deployment")
    for label, predicates in (("historical", before), ("corrected", after)):
        campaign.run([campaign.sys.executable, campaign.ROOT / "examples/tools/build.py", "--change-plan", "rescore",
                      "--report", report, "--bundle", bundle, "--predictions", predicates, "--output", work/(label+".json")])
    old, new = [campaign.read(work / (label+".json"))["claims"][0] for label in ("historical", "corrected")]
    if (old["status"], new["status"]) != ("open", "established") or not (
            old["observationsSha256"] == new["observationsSha256"] and old["receipt"] == new["receipt"] == node["receipt"]):
        raise ValueError("the fresh lone question failed offline re-evaluation of its original public returns")
    campaign.pack(work, [bundle, *work.glob("*.json"), work/"receipts"], campaign.HERE/"receipts/458-format-rescore.zip")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--live", action="store_true", help="qualify a single newly registered wrong parent on the original JVMs")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="observer-offline-rescore-") as tmp:
        if args.live:
            live(Path(tmp))
            return
        rows = {case: evaluate(case, Path(tmp) / case) for case in ("06", "466")}
    out = campaign.HERE / "baseline-rescores.json"
    if args.check:
        if rows != campaign.read(out):
            raise ValueError("offline evaluation differs from the saved record")
    else:
        campaign.write(out, rows)
    print("Two original open baselines, two established corrections, two refuted fix controls.")


if __name__ == "__main__":
    main()
