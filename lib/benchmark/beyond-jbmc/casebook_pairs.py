"""Score the same observation on both sides, and count overlapping release comparisons explicitly."""
from collections import Counter,defaultdict
from scores import DECISIONS,partition


def compare_releases(tasks):
    rows=defaultdict(dict)
    for entry in tasks.values():
        for claim in entry["properties"]:
            source=claim.get("measurement")
            if source:
                key=(entry["id"],claim["method"])
                rows[source][key]=claim
    pairs={}
    def record(name,groups):
        observations=[]
        for comparison in groups:
            predicates=[rows[label] for label in comparison]
            if not all(predicates):raise ValueError("missing release comparison: "+", ".join(comparison))
            shared=set.intersection(*(set(p) for p in predicates))
            if not shared or any(set(p)!=shared for p in predicates):
                raise ValueError("asymmetric release observations: "+", ".join(comparison))
            for key in sorted(shared):
                sides=[p[key] for p in predicates]
                states={engine:[s[engine]["disposition"] for s in sides] for engine in ("native","integrated","stock")}
                # One qualified profile must answer the whole observation on the pair.
                correct={e:all(v in DECISIONS for v in values) for e,values in states.items()}
                observations.append({"task":key[0],"method":key[1],"measurements":comparison,"dispositions":states,
                                     "correct":correct,"partition":partition(correct["native"],correct["integrated"] or correct["stock"])})
        if not observations:return
        counts=Counter(r["partition"] for r in observations)
        pairs[name]={"observations":observations,"counts":counts,"oneVoteAll":partition(
            all(r["correct"]["native"] for r in observations),all(r["correct"]["integrated"] or r["correct"]["stock"] for r in observations))}
    def direct(name,*lanes):record(name,[[lane] for lane in lanes])
    direct("Lucene 8.11.0 → 9.0.0","wire","W03","W08","W09-reordered")
    direct("Protobuf 3.25.5 → 4.33.0","W06","W07")
    direct("Protobuf writer and Lucene reader","W05")
    direct("Jackson Core/Databind 2.17.1 → 2.17.2","N11-core","N11-quoted","N11-identity","N11-extended")
    for lane,name,old,new in (
        ("N08","Commons Numbers","1.1","1.2"),("N09","JTS","1.18.2","1.20.0"),
        ("H04","PCollections","3.1.4","4.0.2"),("H08","jsoup","1.18.1","1.18.2"),("H09","jsoup","1.18.2","1.18.3"),
        ("C08","Semver4j","5.6.0","5.7.0")):
        record(f"{name} {old} → {new}",[[lane+"-"+old,lane+"-"+new]])
    for lane,versions in (("H05-H06",("1.6.15","1.6.16","1.6.17","1.6.18")),("H07",("1.6.25","1.6.26","1.6.27","1.6.28"))):
        for old,new in zip(versions,versions[1:]):
            record(f"RoaringBitmap {old} → {new}",[[lane+"-"+old,lane+"-"+new]])
    for a,b in (("1.13","1.14"),("1.14","1.15"),("1.13","1.15")):
        direct(f"Commons Codec {a} → {b}","C01-C05-"+a+"-"+b)
    for old,new in (("6.1.3","6.1.14"),("6.1.14","6.2.0"),("6.2.0","6.2.3")):
        groups=[["S04-S06-"+old,"S04-S06-"+new]]
        if old=="6.1.14":groups+=[["S02-S09-old","S02-S09-new"],*[[lane+"-"+old,lane+"-"+new] for lane in ("S03","S07","S08")]]
        record(f"Spring {old} → {new}",groups)
    record("Joda-Time 2.12.0 → 2.12.1",[["joda-time-2.12.0","joda-time-2.12.1"]])
    record("Semver4j 6.0.0 → 6.1.0",[[lane+"-6.0.0",lane+"-6.1.0"] for lane in ("C09","C10")])
    return pairs
