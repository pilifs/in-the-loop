"""Bind and rank production calls witnessed by an original test JVM."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import zipfile

from targets import runtime_jar, upgrade_replay


def method_frame(text):
    loader, bci, exported, receiver, member = text.split(" ",4)
    return {"member":member,"loader":int(loader),"bci":int(bci),"public":exported=="1","receiver":int(receiver)}


def handoffs(fork, declarations, changed, *, withhold=()):
    """Join a subscription, dispatch, queued Runnable, worker invocation and the original changed-body stack."""
    subscriptions, sources, requested, queued, running, deliveries = {}, {}, {}, {}, {}, {}
    cancelled = set()
    hits = []
    for serial,event in enumerate(fork["sequence"],1):
        kind, thread, _, *parts = event
        if kind == "tap":
            role, loader, target, caller, pc, instance, *extra = parts
            if target != declarations.get(role):
                raise ValueError("unregistered handoff action")
            boundary = extra.index("STACK")
            values = list(map(int,extra[:boundary]))
            stack = [method_frame(s) for s in extra[boundary+1:]]
            instance = int(instance)
            if role == "subscribe" and values[0] > 0:
                subscriptions[values[0]] = (target,instance)
            elif role == "register":
                ticket, source = values
                if min(ticket,source)>0 and any((f["member"],f["receiver"]) == subscriptions.get(ticket) for f in stack):
                    sources[ticket] = source
            elif role == "dispatch":
                ticket, source, task = values
                if min(ticket,source,task)>0 and sources.get(ticket) == source:
                    requested[task] = (ticket,source,serial)
            elif role == "queue":
                task, = values
                if (task in requested and task not in withhold and
                        any(f["member"] == declarations["dispatch"] for f in stack)):
                    queued[task] = (*requested[task],serial,thread)
            elif role == "run":
                if instance in queued:
                    running[instance] = (*queued[instance],serial,thread)
            elif role == "deliver":
                ticket,source = values[:2]
                for frame in stack:
                    task = frame["receiver"]
                    state = running.get(task)
                    if frame["member"] == declarations["run"] and state and state[:2] == (ticket,source) and state[-1] == thread:
                        deliveries[task] = (*state,serial)
                        break
            elif role == "cancel":
                cancelled.add(instance)
        elif kind == "hit":
            frames = [method_frame(s) for s in parts[1:]]
            if not frames or frames[0]["member"] not in changed:
                continue
            delivery = next((f for f in frames if f["member"] == declarations["run"]),None)
            if not delivery:
                continue
            task = delivery["receiver"]
            state = deliveries.get(task)
            hit = {"event":serial,"changed":frames[0]["member"],"worker":thread,"task":task,"status":"unattributed"}
            if state:
                ticket,source,dispatch,enqueue,dispatch_thread,start,worker,deliver = state
                if (ticket not in cancelled and worker == thread and worker != dispatch_thread and
                        any(f["receiver"] == source and f["member"].partition("#")[2].startswith("next(") for f in frames)):
                    hit.update(status="attributed",ticket=ticket,source=source,dispatch=dispatch,queued=enqueue,
                               started=start,delivered=deliver,relationship="observed subscription and queued handoff")
            hits.append(hit)
    return {"registered":sources,"cancelled":sorted(cancelled),"hits":hits}


def read_fork(path, graph, test_classes, test_module, revision, jdk_pin, feature):
    """Each original loaded definition must match the physical bytes and source of this fork."""
    roots = [Path(r["file"]).resolve() for r in graph]
    logs = path.with_suffix(".loads")
    origins = upgrade_replay.class_origins(logs.read_text(errors="replace")) if logs.is_file() else {}
    classes = {}
    keys = {}
    sequence = []
    stopped = "VM did not record shutdown"
    with path.with_suffix(".classes").open("rb") as image:
        for line in path.read_text().splitlines():
            fields = line.split("\t")
            if fields[0] == "CLASS":
                ident, offset, size = fields[1:]
                loader, owner = ident.split(":",1)
                image.seek(int(offset))
                data = image.read(int(size))
                if len(data) != int(size) or runtime_jar.this_class(data) != owner:
                    raise ValueError("truncated or mismatched original class-load bytes")
                sha = hashlib.sha256(data).hexdigest()
                prior = keys.setdefault((int(loader),owner),sha)
                if prior != sha:
                    raise ValueError("class bytes changed on a single defining loader")
                providers = origins.get(owner.replace("/","."),set())
                chosen = None
                if len(providers) == 1 and (location := next(iter(providers))) in roots:
                    idx = roots.index(location)
                    expected = ((location/(owner+".class")).read_bytes() if location.is_dir()
                                else runtime_jar.effective_class(location,owner,feature))
                    if expected == data:
                        chosen = {"providerIndex":idx,"artifactSha256":graph[idx]["sha256"]}
                from_test = providers == {test_classes.resolve()} and (test_classes/(owner+".class")).is_file()
                if from_test and (test_classes/(owner+".class")).read_bytes() != data:
                    raise ValueError("loaded upstream test differs from its original class file")
                classes[ident] = {"owner":owner,"definingLoader":int(loader),"classSha256":sha,
                                  "upstreamTest":from_test,"originalProvider":chosen}
            elif fields[0] == "LIMIT":
                stopped = "raw event limit reached"
            elif fields[0] == "END":
                if fields[2] == "0" and int(fields[1]) == len(sequence):
                    stopped = None
            else:
                if int(fields[0]) != len(sequence)+1:
                    raise ValueError("non-contiguous original test event sequence")
                sequence.append(fields[1:])
    return {"revision":revision,"jdkReleaseSha256":jdk_pin,"module":test_module,"rawFile":path.name,
            "rawSha256":upgrade_replay.sha(path),"loadOriginsSha256":upgrade_replay.sha(logs) if logs.is_file() else None,
            "classBytesSha256":upgrade_replay.sha(path.with_suffix(".classes")),
            "sequence":sequence,"classes":classes,"stop":stopped}


def witnesses(fork):
    tests, open_calls, finished = {}, {}, defaultdict(list)
    rows = []
    classes = fork["classes"]
    def binding(loader,member):
        return classes.get(str(loader)+":"+member.partition("#")[0],{})
    for serial, event in enumerate(fork["sequence"],1):
        kind, thread, test, *fields = event
        key = (thread,test)
        if kind == "test":
            tests[key] = fields[0]
            continue
        if key not in tests:
            continue
        if kind == "entry":
            call, receiver, loader, member, caller_loader, caller, bci = fields
            if binding(loader,member).get("originalProvider") and binding(caller_loader,caller).get("upstreamTest"):
                open_calls[(thread,call)] = {"entry":member,"receiver":int(receiver),"loader":int(loader),
                    "caller":caller,"callerBci":int(bci),"began":serial}
        elif kind == "exit":
            call, outcome = fields
            previous = open_calls.pop((thread,call),None)
            if previous and outcome == "return":
                finished[key].append({**previous,"returned":serial})
            if call == test:
                finished.pop(key,None)
        elif kind == "hit":
            frames = [method_frame(f) for f in fields[1:]]
            if not frames or not binding(frames[0]["loader"],frames[0]["member"]).get("originalProvider"):
                continue
            candidates = []
            test_seen = False
            for frame in frames:
                b = binding(frame["loader"],frame["member"])
                if b.get("upstreamTest"):
                    test_seen = True
                    break
                if b.get("originalProvider") and frame["public"]:
                    candidates.append(frame)
            if not candidates or not test_seen:
                continue
            context = {"test":tests[key],"testInvocation":test,"thread":thread,"module":fork["module"],
                       "hitEvent":serial,"changed":frames[0]["member"],"actualFrames":frames}
            boundary = candidates[-1]
            rows.append({**context,"entry":boundary["member"],"relationship":"nested","frame":boundary})
            receivers = {(f["loader"],f["receiver"]) for f in frames if f["receiver"]>0}
            latest = {}
            for call in reversed(finished[key]):
                if (call["loader"],call["receiver"]) in receivers and call["entry"] != boundary["member"]:
                    latest.setdefault(call["entry"],call)
            rows.extend({**context,"entry":entry,"relationship":"later on retained receiver","publicCall":call}
                        for entry,call in latest.items())
    return rows


def rank(traces, sides=("old","new")):
    evidence = defaultdict(lambda:defaultdict(lambda:{"nested":set(),"later":set(),"sides":set()}))
    for side in sides:
        for run in traces[side]:
            if not run["plainParity"] or run["fork"]["stop"] is not None:
                continue
            for row in run["witnesses"]:
                observed = evidence[row["module"]][row["entry"]]
                observed["sides"].add(side)
                observed["nested" if row["relationship"] == "nested" else "later"].add(row["test"])
    per_module = {}
    all_rows = []
    for module, entries in sorted(evidence.items()):
        rows = []
        for entry, coverage in entries.items():
            owner, _, member = entry.partition("#")
            rows.append({"entry":owner.replace("/",".")+"#"+member,
                         "module":module,"nestedTests":sorted(coverage["nested"]),"laterTests":sorted(coverage["later"]),
                         "sides":sorted(coverage["sides"])})
        per_module[module] = sorted(rows,key=lambda r:(-len(r["sides"]),-len(r["nestedTests"]),
            -len(set(r["nestedTests"]+r["laterTests"])),r["entry"]))
        all_rows.extend(per_module[module])
    ordered = [rs[0] for rs in per_module.values() if rs]
    for row in sorted(all_rows,key=lambda r:(-len(r["sides"]),-len(r["nestedTests"]),
                       -len(set(r["nestedTests"]+r["laterTests"])),r["entry"])):
        if not any(prior["entry"] == row["entry"] for prior in ordered):
            ordered.append(row)
    return [{**r,"rank":i} for i,r in enumerate(ordered,1)]


def apply(inventory, paths, views, launches, jdks):
    """Replay original event order and check observed class bytes against the current Stage 2 inputs."""
    from collections import Counter
    sessions = defaultdict(list)
    sources = []
    for path in paths:
        with zipfile.ZipFile(path) as z:
            doc = json.loads(z.read("summary.json"))
            side = doc["side"]
            if (doc.get("schema") != "original-upstream-history/v1" or side not in views
                    or doc["revision"] != launches[side]["production"].get("commit")
                    or doc["jdkReleaseSha256"] != upgrade_replay.sha(jdks[side]/"release")
                    or [r["sha256"] for r in doc["orderedDeployment"]] != views[side].hashes):
                raise ValueError("upstream trace belongs to another revision, JDK or ordered deployment")
            for run in doc["runs"]:
                if not run["plain"] or run["plain"] != run["traced"]:
                    continue
                for stored in run["forks"]:
                    fork = dict(stored["fork"])
                    directory = fork.get("rawDirectory",fork["module"]+"-traced")
                    raw = z.read(directory+"/"+fork["rawFile"])
                    if hashlib.sha256(raw).hexdigest() != fork["rawSha256"]:
                        raise ValueError("upstream raw test events changed")
                    stem = directory+"/"+Path(fork["rawFile"]).stem
                    originals = z.read(stem+".classes")
                    loads = z.read(stem+".loads")
                    if (hashlib.sha256(originals).hexdigest() != fork["classBytesSha256"]
                            or hashlib.sha256(loads).hexdigest() != fork["loadOriginsSha256"]):
                        raise ValueError("the JVM class-load inputs changed")
                    for line in raw.decode().splitlines():
                        if line.startswith("CLASS\t"):
                            _, ident, start, size = line.split("\t")
                            data = originals[int(start):int(start)+int(size)]
                            if hashlib.sha256(data).hexdigest() != fork["classes"][ident]["classSha256"]:
                                raise ValueError("the exact loaded bytes differ from the stored binding")
                    for b in fork["classes"].values():
                        provider = b["originalProvider"]
                        if provider:
                            winner = views[side].winners.get(b["owner"])
                            if (not winner or winner[0] != provider["providerIndex"] or winner[1].sha != b["classSha256"]
                                    or views[side].hashes[winner[0]] != provider["artifactSha256"]):
                                raise ValueError("the observed test action differs from its current winning provider")
                    fork["sequence"] = [line.split("\t")[1:] for line in raw.decode().splitlines() if line.partition("\t")[0].isdigit()]
                    if len(fork["sequence"]) != fork["events"]:
                        raise ValueError("incomplete upstream raw sequence")
                    sessions[side].append({"plainParity":True,"fork":fork,"witnesses":witnesses(fork)})
            sources.append({"side":side,"sha256":upgrade_replay.sha(path),"revision":doc["revision"],
                            "policySha256":doc["policySha256"]})
    rows = rank(sessions)
    by_entry = {r["entry"]:r for r in inventory["candidates"]}
    reordered = []
    for row in rows:
        entry = row["entry"]
        r = dict(by_entry.get(entry,{"entry":entry,"sides":{},"independentlyDiscovered":True}))
        r["staticRank"] = r.get("rank")
        r["observedRank"] = row["rank"]
        r["originalTestCoverage"] = row
        reordered.append(r)
    reported = {r["entry"] for r in reordered}
    for row in inventory["candidates"]:
        if row["entry"] not in reported:
            reordered.append({**row, "staticRank": row.get("rank")})
    for position, row in enumerate(reordered, 1):
        row["rank"] = position
    inventory["upstreamHistory"] = {"sources":sources,"ranked":rows,"qualifiedForks":dict(Counter(
        side for side, runs in sessions.items() for r in runs if r["fork"]["stop"] is None))}
    inventory["candidates"] = reordered
    inventory["candidateCount"] += len(reported-set(by_entry))
    if len(rows)>1:
        inventory["intentQuestion"] = "Which original public observation matters to the caller: " + " or ".join(r["entry"] for r in rows[:3]) + "?"
    return inventory
