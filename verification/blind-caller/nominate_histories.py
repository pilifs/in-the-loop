"""Seal trace nominations without reading the historical callers, observations or nominated entry names."""
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/"examples/tools"))
from targets import blind_prediction, public_histories, upgrade_replay


def nominate():
    traces = {}
    inputs = {}
    summaries = {}
    for side in ("old","new"):
        path = HERE/("parquet-"+side+".zip")
        inputs[side] = upgrade_replay.sha(path)
        with zipfile.ZipFile(path) as z:
            doc = json.loads(z.read("summary.json"))
            if doc["reversedOverlay"] or doc["policySha256"] != upgrade_replay.sha(HERE/"trace-policy.json"):
                raise ValueError("wrong ordered graph or ranking policy")
            traces[side] = []
            summaries[side] = []
            for run in doc["runs"]:
                for record in run["forks"]:
                    fork = record["fork"]
                    raw = z.read(fork["module"]+"-traced/"+fork["rawFile"])
                    if blind_prediction.digest(raw) != fork["rawSha256"]:
                        raise ValueError("the original event sequence changed")
                    fork["sequence"] = [line.split("\t")[1:] for line in raw.decode().splitlines() if line.partition("\t")[0].isdigit()]
                    traces[side].append({"plainParity":run["plain"]==run["traced"],"fork":fork,"witnesses":public_histories.witnesses(fork)})
                    summaries[side].append({"module":run["module"],"upstreamTests":len(run["plain"]),
                                            "plainParity":run["plain"]==run["traced"],"stop":fork["stop"],
                                            "events":len(fork["sequence"])})
    return {"schema":"public-history-nominations/v1","policySha256":upgrade_replay.sha(HERE/"trace-policy.json"),
            "archives":inputs,"originalTestCoverage":summaries,"candidates":public_histories.rank(traces)}


if __name__=="__main__":
    result=nominate()
    blind_prediction.publish(HERE/"first-nominations.json",result)
    print("sealed",len(result["candidates"]),"original public entries before comparison")
