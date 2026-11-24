"""Assemble the 68 disclosed work items without counting sibling predicates as independent upgrades."""
import argparse
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
from history import HERE,ROOT,OUTPUT,encoded,digest
from scores import qualified,DECISIONS,partition,costs

def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix==".gz" else p.read_bytes())

def assign(key,method,row):
    if key=="wire":return row["case"]
    if key.startswith("W"):return key[:3]
    if key=="N01-N02":return "N02" if method in ("underflow","positive") else "N01"
    if key=="N04-N05":return "N04" if method.endswith("Range") else "N05"
    if key.startswith("N"):return key[:3]
    if key.startswith("H05-H06"):return "H05" if method=="forward" else "H06"
    if key=="H10-H14-supplied":
        return dict(planes="H10",conditional="H11",unconditional="H11",scalar="H12",dispatch="H13",noSelf="H14")[method]
    if key.startswith("H"):return key[:3]
    if key=="E01-E03":return "E01" if method=="coarse" else "E03"
    if key.startswith("S02-S09"):return "S09" if method in ("afterClear","releasedSignature") else "S02"
    if key.startswith("S04-S06"):return {"bridge":"S04","aliases":"S05","conversion":"S06"}[method]
    if key.startswith("S"):return key[:3]
    if key.startswith("C01-C05"):return "C05" if method=="unchanged32" else "C01"
    if key=="C03-C04":return "C03" if method=="chunks" else "C04"
    if key.startswith("C"):return key[:3]
    if key in ("joda-time-2.12.0","joda-time-2.12.1"):return "C07" if method=="unaffected" else "C06"
    raise ValueError((key,method))

# Each entry defines the unit of replication and the application or benchmark scope.
GROUPS={
 "W01-W02-W03-W04-W08-W09":"Lucene 8.11.0 → 9.0.0",
 "W05":"Protobuf ↔ Lucene", "W06-W07":"Protobuf 3.25.5 → 4.33.0",
 "N01-N02-N03":"vecmath 1.5.2", "N04-N05":"Jackson Core 2.19.0", "N06-H01-H02-H03-H10":"Commons Lang 3.17.0",
 "N07":"Guava 33.4.8-jre and Commons Lang 3.17.0","N08":"Commons Numbers 1.1 → 1.2",
 "N09":"JTS 1.18.2 → 1.20.0","N10":"Commons Math 3.6.1","N11":"Jackson 2.17.1 → 2.17.2",
 "H04":"PCollections 3.1.4 → 4.0.2","H05-H06":"RoaringBitmap 1.6.16 → 1.6.17 and neighbors",
 "H07":"RoaringBitmap 1.6.26 → 1.6.27 and neighbors","H08":"jsoup 1.18.1 → 1.18.2","H09":"jsoup 1.18.2 → 1.18.3",
 "H11-H12-H13-H14":"Constructed heap fixtures","E01-E02-E03":"Constructed exception histories","S01":"JDK generic metadata fixture",
 "S02-S03-S04-S05-S06-S07-S08-S09":"Spring release families and separately bound historical binder",
 "C01-C05":"Commons Codec 1.13 → 1.14 → 1.15","C02-C03-C04":"Commons Codec 1.15",
 "C06-C07":"Joda-Time 2.12.0 → 2.12.1","C08":"Semver4j 5.6.0 → 5.7.0","C09-C10":"Semver4j 6.0.0 → 6.1.0"}
ANNOTATIONS={
"W01":"All signed ints, both local identities and both mixed reversals. Compatible iff the four bytes form a palindrome.",
"W02":"Every byte and cursor at valid offsets on aliased inputs up to eight bytes. Guava FarmHash is the separate transfer.",
"W03":"All signed shorts and longs, both mixed directions. Four stock inputs satisfied the original predicates.",
"W04":"All int bit patterns, both mixed directions, unsigned seven-bit-group length and next unread byte.",
"W05":"The Protobuf writer and Lucene reader agree on bytes and consumption. The swapped signed entry has a five-versus-ten byte witness.",
"W06":"Two changed size implementations versus an independent shift oracle, UInt32 and UInt64.",
"W07":"Both directions for UInt32, UInt64 and ZigZag on exact-sized records. The stock unsigned proofs and disputed ZigZag witnesses have different dispositions.",
"W08":"Fixed header plus independent VInt payload in both directions, including separate value, suffix and position checks.",
"W09":"The sequence theorem and alternate field-order experiment are separate from an unrestricted released Java loop.",
"N01":"Two independent binary32 factors, 2⁴⁶ pairs, range and sign-related companion. The unrounded double-product sibling is false.",
"N02":"Two independent binary32 factors, 2⁴⁶ pairs. Exact zero boundary and three possible rounded underflow results.",
"N03":"Two component scaleAdd with 2,048 cancellation inputs. Positive-zero bits through n=1,448, then the negative predecessor spacing.",
"N04":"Every suffix 000–999, either sign, String and char-array slices at offsets 0–2.",
"N05":"The accepted threshold family and the general 19-ASCII-digit input within the 24-unit array bound are reported separately.",
"N06":"All 65,536 code units after 0. The Commons Unicode-digit predicate and the joint Double.parseDouble partition are separate claims.",
"N07":"Two independently symbolic UTF-16 units, real String and custom CharSequence, both libraries and argument directions, plus null controls.",
"N08":"Signed zeros and separately boxed NaN bits. Equality, emitted hashes, ordering, raw bits and reflexive cases distinguish the profiles.",
"N09":"Signed-coordinate box [−8,8] and a separate large near-collinear family of integer determinants one. Both point orders and releases.",
"N10":"Two independent binary64 factors, 2¹⁰⁴ pairs, three subnormal-or-zero results on the public fresh-vector call.",
"N11":"Exact 11,111-string Core partition, separate null control and four public quoted-token consumers. Original JVMs exhaust the finite domain.",
"H01":"Direct Cell[] inputs and explicit null, shared and distinct MutableInt payloads. Java int wraparound included.",
"H02":"Three publicly linked MutableObjects, 64 successor graphs × four starts. The self-link-only detector misses a two-node cycle.",
"H03":"Two public MutableObject roots, equal values or identical MutableInt tails, an untouched sibling and arbitrary initial int.",
"H04":"Two persistent vector branches, lengths 1–6, all valid indices and arbitrary replacement int, with checks after every operation.",
"H05":"Forward clone through six steps and a container boundary. Versions 1.6.15/16 and 1.6.17/18 retain the neighbor observations.",
"H06":"Reverse clone-only and alternating histories, both cursors and exhaustion. Older releases also have a physically observed bounds exception.",
"H07":"Range and subset overloads are distinct. The changed query requires a bitmap superset and run subset, tested across 9,994 hole positions.",
"H08":"Element and HTML append, subsequent removal, and independent live reparenting on real FormElement objects.",
"H09":"Serialize and reparse the attribute aXa for lower-case letters, decimal digits, underscore, dot and hyphen.",
"H10":"Plane identities before and after ArrayUtils.reverse(Object[]), including aliasing. Directly supplied and constructed arrays have separate receipts.",
"H11":"Two Flat[] roots, both alias choices. The conditional frame and the deliberately false unconditional frame exercise different input models.",
"H12":"A Flat[] slot and a scalar root, including shared entry at MAX_VALUE. Observe both identity and wrapped mutation.",
"H13":"Three concrete runtime types dispatched through a base array. The corresponding real registration transfer also appears in S06.",
"H14":"Null tail, self-link and two-node cycle. A proof about independent generated trees cannot establish absence of Java self-links.",
"E01":"All three original modes, caller and callee top frames, independent occurrence and escape selection and the coarse result.",
"E02":"Mode zero constructs the receiver. The same exception now originates inside read. The helper variant and repaired original sites have separate receipts.",
"E03":"Same-instance rethrow and newly allocated NPE with their physical throw frames, saved identity and catch history.",
"S01":"Local parameterized interface, nested wildcard, equality, defensive copies of each array and an actual inverse control.",
"S02":"Original String/Integer/String generic resolutions on both released frameworks. The transferred nested signature proof covers only part of this path.",
"S03":"The original annotated and preservation binder histories, the real EnumToStringConverter at registration, two releases and historical source slices.",
"S04":"Cold and warm lookup of an actual bridge among String and Integer declarations on four Spring releases.",
"S05":"Merged alias values, direct annotation absence and unequal explicit aliases on four Spring releases.",
"S06":"Empty, add, replace, remove and re-add histories. The second service remains untouched.",
"S07":"Actual listener matching for List<T>, T, List<String> and String, on both listener types and both releases.",
"S08":"Two assembler registrations, four optional injection sites, four registration orders and bean identities on each release.",
"S09":"Mutate all three reflection arrays, clear the framework cache and revisit the full public ResolvableType path.",
"C01":"Three pairings with both 128-bit result words and all signed seeds on bounded arrays. The exact sign-boundary conjecture is separate.",
"C02":"Signed-negative tail condition for the original 32-bit and canonical x86 hashes over bounded slices. Sampled agreement does not prove collision freedom.",
"C03":"One-shot versus two arbitrary chunks, repeated end, seed and input frame within the eight-byte input bound.",
"C04":"Three chunks after a partial reset and an independently specified arbitrary-partition streaming model. Java execution and model induction are distinct.",
"C05":"Old, warm and clean new checks. The unchanged 32-bit wrapper reuses its proof. A 128-bit result at seed −1 invalidates stale evidence.",
"C06":"Original bundled provider in UTC 2023, both transition endpoints and month controls. Shared class bytes coexist with a changed zone payload.",
"C07":"Seeded unaffected zone among 439 identical payloads. Its own provider alias entry agrees while the complete ZoneInfoMap file differs.",
"C08":"One to three groups, values 0–19 and independent leading-zero bits. Includes the plain-text rejection.",
"C09":"Normalized digit precedence through 20 digits with exact NumberFormatException versus return transitions at the signed-long boundary.",
"C10":"All 16 combinations of four zero caret ranges and four version boundary points."}


def program(root,key,replays):
    p=root/"opening/svcomp"/key/"result.json.gz";d=read(p)
    x={"method":d["task"],"expected":"verified" if d["expected"] else "violation","receipt":str(p.relative_to(root))}
    for k,dest in (("native","native"),("jbmc","integrated")):
        v=d[k];out=v.get("verdict")
        state="proved" if out=="verified" and d["expected"] else "incorrect proof" if out=="verified" else "witness unconfirmed" if out=="violation" else "open"
        x[dest]={"disposition":state,"literal":out,"firstProblem":v.get("problem"),"cost":{f:v.get(f) for f in ("seconds","cpuSeconds","peakMB")}}
    t=d["stock"];repro=[a for a in replays if a["case"]==key]
    if repro and all(a["disposition"]=="stock counterexample confirmed" for a in repro):state="refuted"
    elif any(a["disposition"]=="stock counterexample did not reproduce" for a in repro):state="incorrect refutation"
    elif t["status"]=="success" and t["targets"] and d["expected"] and any(y["status"]=="FAILURE" for y in d["stockReach"]["targets"]):state="proved"
    elif t.get("otherFailures"):state="incomplete unwinding" if any("unwind" in q or "recursion" in q for q in t["otherFailures"]) else "other failed property"
    else:state=t["status"]
    x["stock"]={"literal":t["status"],"disposition":state,"target":t["targets"],"firstProblem":t.get("otherFailures"),"cost":{f:t.get(f) for f in ("seconds","cpuSeconds","peakMB")}}
    x["competition"]=d["competition"];x["sourceSha256"]=d["sourceSha256"];x["registeredJvm"]=d["jvm"];x["stockReplay"]=repro
    return x


def build(root,out):
    manifest=read(HERE/"casebook.json")
    cases={r["id"]:dict(r,properties=[],additionalEvidence=[]) for r in manifest["tasks"]}
    if len(cases)!=68:raise ValueError("wrong casebook denominator")
    for group,label in GROUPS.items():
        for key in group.split("-"):cases[key]["unit"]=label
    for f in sorted((root/"qualified").glob("**/results.json.gz")):
        raw=read(f)
        if not isinstance(raw,dict) or "rows" not in raw:continue
        key=f.parent.name
        for r in raw["rows"]:
            cid=assign(key,r["method"],r);q=qualified(r)
            q["measurement"]=key;q["receipt"]=str(f.relative_to(root));q["receiptSha256"]=digest(f)
            if key=="H10-H14-supplied" and r["method"] in ("unconditional","noSelf"):
                for eng in ("native","integrated","stock"):
                    if q[eng]["literal"] in ("verified","SUCCESS"):
                        q[eng]["disposition"]="default generated roots only; broader alias or cycle scope unmatched"
            cases[cid]["properties"].append(q)
    replay=read(OUTPUT/"opening/svcomp-stock-replays.json")
    for i in range(1,13):
        key=f"B{i:02}";x=program(root,key,replay);cases[key]["unit"]=x["method"];cases[key]["properties"].append(x)
    related={
        "E01":["qualified/E-sites/sites.json.gz"],"E02":["qualified/E-sites/sites.json.gz"],"E03":["qualified/E-sites/sites.json.gz"],
        "W09":["assurance/wire-calculus.json","assurance/wire-sequence/receipt.json"],"C04":["assurance/codec-sequence/receipt.json"],
        "C01":["assurance/seed-sequence/receipt.json"],
        "C05":["qualified/C01-C05-1.14-1.15/cache.json"],"C06":["qualified/C06-C07/reuse.json.gz","qualified/C06-C07-equality/result.json.gz"],
        "C07":["qualified/C06-C07/reuse.json.gz","qualified/C06-C07-equality/result.json.gz"],"H11":["qualified/H11-may-alias/results.json"],
        "S03":["examples/374-spring-formatter-binding/records/beyond-jbmc-frozen/run.json"],
        "S09":["examples/368-spring-binding-history/records/beyond-jbmc-frozen/run.json"],
    }
    totals=defaultdict(Counter);groups=defaultdict(Counter);flat=[]
    for key,row in cases.items():
        row["scope"]=ANNOTATIONS.get(key,"Original nondeterminism and valid-assert property, JDK 21, 120-second local checker budget.")
        for rel in related.get(key,[]):
            path=(root.parents[1] if rel.startswith("examples/") else root)/rel
            if path.is_file():row["additionalEvidence"].append({"file":rel,"sha256":digest(path)})
        rows=row["properties"];flat.extend(rows)
        row["qualified"]={e:sum(p[e]["disposition"] in DECISIONS for p in rows) for e in ("native","integrated","stock")}
        for p in rows:
            n=p["native"]["disposition"] in DECISIONS;j=any(p[e]["disposition"] in DECISIONS for e in ("integrated","stock"))
            groups[row["unit"]][partition(n,j)]+=1
            for e in ("native","integrated","stock"):totals[e][p[e]["disposition"]]+=1
    complete_units=Counter()
    for c in groups.values():
        total=sum(c.values())
        all_native=bool(total) and c["both"]+c["native-only"]==total
        all_comparator=bool(total) and c["both"]+c["comparator-only"]==total
        complete_units[partition(all_native,all_comparator)]+=1
    out.mkdir(parents=True,exist_ok=True)
    (out/"matrix.json.gz").write_bytes(gzip.compress(encoded({"tasks":list(cases.values()),"units":groups,
        "allMeasuredPropertiesByReplicationUnit":complete_units,"propertyCounts":totals,"matchedCosts":costs(flat)}),mtime=0))
    md=["# Disclosed casebook","","The 68 rows are work items. Columns count qualified property results within the measured scopes. A proved helper or a bounded model has its own statement. The same release pair supplies several work items. The data file retains each literal comparison, failed control, JVM replay, cost and underlying receipt. [Full matrix](matrix.json.gz)","","| ID | Measured scope | Properties | Native | Integrated | Stock |","|---|---|---:|---:|---:|---:|"]
    for key,r in cases.items():
        q=r["qualified"];md.append(f"| {key} | {r['scope']} | {len(r['properties'])} | {q['native']} | {q['integrated']} | {q['stock']} |")
    md+=["","The following rows group property decisions by library upgrade or independent benchmark program. Each number still counts predicates in the indicated unit. A unit with several predicates contributes one project to transfer claims.","","| Release pair or corpus task | Both | Native only | Comparator only | Neither |","|---|---:|---:|---:|---:|"]
    for unit,c in groups.items():md.append("| "+unit+" | "+" | ".join(str(c[k]) for k in ("both","native-only","comparator-only","neither"))+" |")
    md+=["",f"Using one vote per release unit or public program, every measured predicate was decided by both profiles in {complete_units['both']} units, by native alone in {complete_units['native-only']}, by an admissible comparator alone in {complete_units['comparator-only']}, and by neither across the entire unit in {complete_units['neither']}. This uses the scopes actually listed in the property table. Unbounded sequence theorems and bytecode occurrence investigations have separate receipts."]
    (out/"RESULTS.md").write_text("\n".join(md)+"\n")
    print(len(cases),"work items,",len(flat),"measured property rows,",len(groups),"replication units")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--inputs",type=Path,default=OUTPUT);p.add_argument("--output",type=Path,default=OUTPUT/"casebook");a=p.parse_args();build(a.inputs,a.output)
