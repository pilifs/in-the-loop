"""Qualify matched Java decisions against the original-domain controls and reproduced witnesses."""
import statistics

DECISIONS={"proved","refuted"}


def replay_state(data):
    if isinstance(data,list):
        states={x.get("outcome") for x in data if x.get("exit")==0}
        return next(iter(states)) if len(states)==1 and all(x.get("exit")==0 for x in data) else None
    if isinstance(data,dict):return data.get("outcome")
    return None


def raw_disposition(data,expected,contrary):
    verdict=data.get("verdict")
    if data.get("killed") or data.get("reason")=="out of time":return "timeout"
    if verdict=="verified":
        if contrary or expected=="violation":return "incorrect proof"
        if data.get("class") not in ("correct",None):return "unqualified proof"
        return "proved"
    if verdict=="violation":
        replay=replay_state(data.get("jvmReplay"))
        if replay=="refuted":return "refuted"
        if replay=="held":return "incorrect refutation"
        return "witness unconfirmed"
    return data.get("reason") or data.get("verdict") or "missing result"


def stock_disposition(stock,expected,contrary):
    t,reach=stock["target"],stock["reach"]
    witness=replay_state(t.get("jvmReplay"))
    if t["status"]=="FAILURE":
        if witness=="refuted":return "refuted"
        if witness=="held":return "incorrect refutation"
        return "witness unconfirmed"
    if t["status"]!="SUCCESS":return t["status"]
    if any("unwind" in p["property"] or "recursion" in p["property"] for p in t.get("otherFailures",[])):
        return "incomplete unwinding"
    if t.get("otherFailures") or t["exit"]!=0:return "other failed property"
    if reach["status"]!="FAILURE":return "false post-call control did not fail"
    if reach.get("otherFailures"):return "post-call control has additional failures"
    if expected=="violation" or contrary:return "incorrect proof"
    return "proved"


def problem_of(d):
    text=d.get("problem","") or ""
    if "strict): " in text:
        text=text.split("strict): ",1)[1]
    if " (the engine" in text:text=text.split(" (the engine")[0]
    return text


def qualified(row):
    expected=row["expected"]
    raw=[row["native"],row["jbmc"],row["stock"]["target"]]
    contrary=any(replay_state(item.get("jvmReplay"))=="refuted" for item in raw)
    result={"method":row["method"],"expected":expected}
    for i,key in enumerate(("native","integrated","stock")):
        data=raw[i]
        state=stock_disposition(row["stock"],expected,contrary) if key=="stock" else raw_disposition(data,expected,contrary)
        o={"literal":data.get("status") if i==2 else data.get("verdict"),"disposition":state,"firstProblem":problem_of(data),
           "cost":{k:data.get(k) for k in ("seconds","cpuSeconds","peakMB","exit","killed")}}
        if data.get("jvmReplay") is not None:o["jvmReplay"]=data["jvmReplay"]
        if key=="stock":
            o["target"]=data.get("target");o["reach"]=row["stock"]["reach"].get("target");o["otherFailures"]=data.get("otherFailures")
            o["targetSuccessContradictedOnOriginalCaller"]=data["status"]=="SUCCESS" and (expected=="violation" or contrary)
        result[key]=o
    return result


def partition(native,other):
    if native:return "both" if other else "native-only"
    return "comparator-only" if other else "neither"


def median(values):
    return round(statistics.median(values),3) if values else None


def costs(rows):
    solved={k:[] for k in ("integrated","stock")}
    for row in rows:
        for k in solved:
            if all(row[e]["disposition"] in DECISIONS for e in ("native",k)):
                solved[k].append((row["native"],row[k]))
    return {k:{"matched":len(pairs),**{field:[median([pair[s]["cost"][field] for pair in pairs
            if pair[s]["cost"].get(field) is not None]) for s in (0,1)] for field in ("seconds","cpuSeconds","peakMB")}}
            for k,pairs in solved.items()}
