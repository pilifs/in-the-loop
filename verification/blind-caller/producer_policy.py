"""Seal exactly the product files a producer may read, independently of evaluator selection and outcomes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGETS = ROOT/"examples/tools/targets"
MODULES = """__init__ approved_test_trace blind_measure blind_prediction change_evidence change_helpers change_inventory
change_plan class_binding deployment_graph entry_binding entry_discovery observer_actions observer_fields observer_fixtures
observer_generation observer_histories observer_io observer_public_data observer_recipes observer_rescore observer_review
observer_scalar observer_state observer_structures public_histories public_observation runtime_jar runtime_jdk
upgrade_claims upgrade_jdbc upgrade_linkage upgrade_receiver upgrade_replay""".split()
JAVA = """GeneratedObservation.java.template PublicHistoryAgent.cpp RuntimeHelperBytes.java UpgradeClassLookup.java
UpgradeObservation.java UpgradeTrace.java""".split()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(checker):
    files = [*(TARGETS/(name+".py") for name in MODULES),*(TARGETS/"java"/name for name in JAVA)]
    return {
        "schema":"blind-caller-producer-policy/v1",
        "sourceFiles":{p.relative_to(ROOT).as_posix():digest(p) for p in sorted(files)},
        "workflowFiles":{p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/"examples/tools/scaffold_example.py",ROOT/"llm-dlc/tools/watch.py")},
        "checkerSha256":digest(checker),"model":None,"prompt":None,
        "predictionSeconds":120,"traceSeconds":180,"measurementSeconds":300,"workflowSeconds":90,
        "candidateBudget":64,"maxRanked":3,"maxProductionTypesPerSide":256,
        "prediction":"One fresh process per arm and case. Static changed-class indexing, first physical definitions on the pinned release, then at most 64 eligible public declarations. Prioritize reviewed names, witnessed original calls, PR-prose names, changed methods, their direct callers, two-sided availability, and binary name. Semantic rank also considers original test references and concrete scalar observation support. Freeze the primary and alternatives, inputs, predicate and receipt identities before measurement.",
        "permissions":"No model or external service. Prediction has no subprocess, network or executable-memory permission. The evaluator excludes its files, historical callers, tests and source checkout from the cold view and records its sentinel denial. Only explicitly reviewed ordinary test inputs may enter the test-assisted trace. Original measurements use an isolated network namespace, the pinned checker, original JDK and neutral artifacts.",
        "domain":"Affirmatively reviewed ordinary product behavior. Preserve scoped abstentions for security-relevant and ambiguous cases. Generated cold scalar calls require closed data operations on both originals and bounded ordinary input literals. The two reviewed NumberFormat and stack recipes use an independently recorded scope decision. Other public entries may bind and stop at a named missing construction or field.",
        "deployment":"Original ordered classpaths, class digests, pin pairs and JDK release are part of each packet. Compile the generated caller against the old public API and run it afresh twice on each original side. Require method and field correspondence before finite adjudication.",
        "selection":"Evaluator's committed eligibility manifest and seed. Draw 5 P, 5 Q and 10 R without replacement, with distinct R projects as eligibility permits. Each selected slot stays in the denominator.",
        "arms":["cold","test-assisted","reviewed","repaired after reveal"],
        "development":["458 retained formatter","J14 reopened index","466 subscription, terminal and callback","484 retained copy",
                       "J08 masked original test coverage","labelled scalar and receipt controls"],
        "ship":{"cold":8,"coldDenominator":20,"crossProjectR":3,"rDenominator":10,"falseQualificationsAllowed":0}}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checker",type=Path,default=ROOT/"lib/target/release/jvmcontract")
    p.add_argument("--output",type=Path,default=HERE/"producer-policy.json")
    p.add_argument("--check",action="store_true")
    a=p.parse_args()
    doc=build(a.checker)
    if a.check:
        if json.loads(a.output.read_bytes()) != doc:
            raise SystemExit("working producer differs from the frozen policy")
    else:
        a.output.write_text(json.dumps(doc,indent=2)+"\n")
    print(len(doc["sourceFiles"]),"frozen product file identities")
