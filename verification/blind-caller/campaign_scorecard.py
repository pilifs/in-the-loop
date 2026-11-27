"""Regenerate the cross-campaign result from independent JVM, evaluator, and backend receipts."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads((HERE/path).read_bytes())


def member(name, entry="qualification.json"):
    with zipfile.ZipFile(HERE/name) as archive:
        return json.loads(archive.read(entry))


def summary():
    population = read("evaluator/score.json")
    repair = read("evaluator/repair-score.json")
    parity = read("url-run/parity.json")
    stage2 = member("stage2-histories-reviewed.zip")
    spring = member("spring-upstream.zip", "coverage.json")
    native = member("strict-helper.zip")
    zone = member("process-zones.zip")
    stock = member("stock-profiles.zip", "profiles.json")
    loaders = member("loader-choices.zip")
    controls = read("evaluator/score-control-evidence.json")
    cache = member("product-controls.zip", "cache-controls.json")
    oracle = member("product-controls.zip","rescore.json")
    receipts = sorted({r["receipt"]["sha256"] for r in oracle})
    if len(receipts) != 1 or len({r["observationsSha256"] for r in oracle}) != 1:
        raise ValueError("the oracle comparisons did not reuse the same measurements")
    all_jobs = read("collector.json")["jobs"]
    if any(not (HERE.parents[1]/o["path"]).is_file() for job in all_jobs for o in job["outputs"]):
        raise ValueError("missing original collector archive")
    evaluator_jobs = [json.loads(f.read_bytes()) for f in sorted((HERE / "evaluator/collector").glob("*.json"))]
    ids = [row["id"] for row in all_jobs] + [row["job"] for row in evaluator_jobs]
    if len(set(ids)) != len(ids):
        raise ValueError("a campaign verification job is counted twice")
    outcomes = {}
    for name in ("J14","466","484"):
        doc = member(name+"-development.zip","application.json")
        outcomes[name] = {r["id"]:r["status"] for r in doc["claims"]}
    subscriptions = {}
    for side in ("old","new"):
        r = member("subscriptions-"+side+".zip","subscriptions.json")
        counts = {}
        for h in r["qualification"]["hits"]:
            counts[h["status"]] = counts.get(h["status"],0) + 1
        subscriptions[side] = {"originalJvm":r["plain"], "handedOffHits":counts,
                               "withheldQueueEvent":r["removedQueueEvidence"]["task"],
                               "upstreamBodyHits":spring["originalTest"][side]["bodyHits"],
                               "upstreamBodyToFluxOnStack":spring["originalTest"][side]["publicEntryOnBodyStack"],
                               "sameThreadStacks":len(spring["sameThread"]["sides"][side])}
    helper = {q:{"finite":r["status"],"originalUses":{s:v["publicSubstitutions"] for s,v in r["sides"].items()},
                 "nativeCallSites":r["sides"]["old"]["nativeUses"]} for q,r in native["variants"]["complete"].items()}
    first = {r["entry"]: r["rank"] for r in read("first-nominations.json")["candidates"]}
    public_ranks = {r["entry"]:{"static":r["staticRank"], "firstSealedOriginalTests":first.get(r["entry"]),
                               "isolatedOriginalTests":r["observedRank"]}
                    for r in stage2["qualifiedChoices"] if r["entry"] in stage2["historicalPublicEntries"]}
    return {
        "schema":"blind-public-caller-campaign/v1",
        "blind": {"producer":population["producerRevision"],"original":population["counts"],
                 "rankAtThree":{a:sum(r["arms"][a]["rankAtThreeQualified"] for r in population["rows"]) for a in population["counts"]},
                 "coldMissStages":population["coldMissStages"],"firstRecurringStops":population["recurringColdGaps"],
                 "shipTargetMet":population["coldNumericalTargetsMet"],
                 "postReveal":{"attempted":repair["attempted"],"qualified":repair["qualified"],"stoppedAt":repair["repair"]["stoppedAt"]},
                 "syntheticFalsifiers":controls["rejected"]},
        "development":{"retainedFormatter":"formatter.zip","publicClaims":outcomes},
        "knownHistoryRecovery":{"parquet":{"rank":public_ranks,"qualifiedForks":stage2["originalTestRanking"]["qualifiedForks"],
                                  "originalAndReversed":"parquet-physical.zip",
                                  "isolatedNominationsPublishedAfterHistoricalComparison":True},"spring":subscriptions},
        "urlTransfer":{"qualifiedDeployments":parity["newQualifiedDeployments"],"totalDeployments":parity["historicalAudit"]["totals"]["deploymentPairs"],
                       "qualifiedQuestions":parity["newQualifiedQuestions"],"historicalQuestions":parity["historicalAudit"]["totals"]["questions"],
                       "verdict":parity["semanticParity"],"perCase":"url-run/parity.json"},
        "historicalAdverse":{r["id"]:r["refuted"] for r in member("historical-adverse.zip","score.json")["questions"]},
        "strictAndProfiled":{"mathMin":helper,"unusedLemma":native["unusedNative"],
                             "timezone":{"originalFinite":zone["finite"],"nextStrictGap":{s:r["fixedProfile"]["problem"] for s,r in zone["log4j"].items()}},
                             "stockJBMC":{s:{"originalJvm":r["originalJvm"],
                                       "verified":sum(p["verdict"]=="verified" for p in r["proofs"]),
                                       "violations":sum(p["verdict"]=="violation" for p in r["proofs"])} for s,r in stock["profiles"].items()},
                             "stockRefusalControls":list(stock["negative"])},
        "ownerReview":{"loaderRestoration":{r["revision"]:r["restoration"] for r in loaders["threeRevisions"]},
                       "missingMapping":loaders["missingMapping"]["ownerDecision"],"alternatives":loaders["choices"],
                       "choice":loaders["ownerDecision"],"stableReviewedMember":"reviewed-entry.zip"},
        "cacheAndRescore":{"actions":{k:r["sides"] for k,r in cache.items()},"oracleVerdicts":[r["status"] for r in oracle],
                           "sharedReceiptSha256":receipts[0]},
        "jobAccounting":{"count":len(ids), "evaluatorArchives":[r["job"] for r in evaluator_jobs],
                         "failedAttempts":[r["id"] for r in all_jobs if r["status"] == "failed"],
                         "preExecutionErrors":[r["id"] for r in all_jobs if r["status"] == "error"]},
        "evidence":{"disclosedAndBackendJobs":"collector.json","originalAndRepairRows":"evaluator/RESULTS.md",
                    "sealedArms":"evaluator/score.json"}
    }


if __name__ == "__main__":
    encoded = (json.dumps(summary(), indent=2) + "\n").encode()
    output = HERE / "campaign-scorecard.json"
    if "--check" in sys.argv[1:]:
        if output.read_bytes() != encoded:
            raise SystemExit("campaign scorecard differs from its underlying receipts")
    else:
        output.write_bytes(encoded)
    print("Campaign scorecard", hashlib.sha256(encoded).hexdigest())
