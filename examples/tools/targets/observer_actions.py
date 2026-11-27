"""Qualify identity, order and public values in a generated multi-operation history."""
import base64
import hashlib
import zipfile

from targets import runtime_jar


def selectors(recipe):
    family = recipe["family"]
    if family == "paired mutable-property samples":
        owner = recipe["owner"]
        getter = "#" + recipe["getter"] + "()Ljava/util/Date;"
        return {"copy": owner + "#<init>(L" + owner.replace(".", "/") + ";)V",
                "copyTo": owner + "#" + recipe["copy"] + "(L" + recipe["target"].replace(".", "/") + ";)V",
                "set": owner + "#" + recipe["setter"] + "(Ljava/util/Date;)V",
                "get": owner + getter, "override": "UpgradeProbe$1" + getter,
                "mutate": "java.util.Date#setTime(J)V", "sample": "UpgradeProbe#millis(Ljava/util/Date;)Ljava/lang/Long;"}
    if family == "consume an event-stream response":
        flux = "reactor.core.publisher.Flux"
        result = "Lreactor/core/publisher/Flux;"
        return {"publisher": recipe["requiredDispatch"], "next": flux + "#doOnNext(Ljava/util/function/Consumer;)" + result,
                "complete": flux + "#doOnComplete(Ljava/lang/Runnable;)" + result,
                "error": flux + "#doOnError(Ljava/util/function/Consumer;)" + result,
                "recover": flux + "#onErrorResume(Ljava/util/function/Function;)" + result,
                "block": flux + "#blockLast(Ljava/time/Duration;)Ljava/lang/Object;",
                "data": recipe["event"] + "#data()Ljava/lang/Object;", "retry": recipe["event"] + "#retry()Ljava/time/Duration;",
                "cause": "java.lang.Throwable#getCause()Ljava/lang/Throwable;", "callback": "UpgradeProbe#lambda$observe$*"}
    if family == "reopened block index and sorted hits":
        t = recipe["types"]
        return {"writer": t["IndexWriter"] + "#<init>(Lorg/apache/lucene/store/Directory;Lorg/apache/lucene/index/IndexWriterConfig;)V",
                "add": t["IndexWriter"] + "#addDocuments(Ljava/lang/Iterable;)J", "close": t["IndexWriter"] + "#close()V",
                "open": t["DirectoryReader"] + "#open(Lorg/apache/lucene/store/Directory;)Lorg/apache/lucene/index/DirectoryReader;",
                "searcher": t["IndexSearcher"] + "#<init>(Lorg/apache/lucene/index/IndexReader;)V",
                "search": t["IndexSearcher"] + "#search(Lorg/apache/lucene/search/Query;ILorg/apache/lucene/search/Sort;)Lorg/apache/lucene/search/TopFieldDocs;",
                "stored": t["IndexSearcher"] + "#storedFields()Lorg/apache/lucene/index/StoredFields;",
                "document": "org.apache.lucene.index.StoredFields#document(I)Lorg/apache/lucene/document/Document;",
                "identifier": t["Document"] + "#get(Ljava/lang/String;)Ljava/lang/String;"}
    return {}


def decode(text):
    return base64.b64decode(text, validate=True)


def optional_constructor(recipe):
    if recipe["family"] == "reopened block index and sorted hits":
        return recipe["owner"] + "#<init>(Ljava/lang/String;Lorg/apache/lucene/search/SortField$Type;ZLjava/lang/Object;Ljava/lang/Object;Lorg/apache/lucene/search/join/BitSetProducer;Lorg/apache/lucene/search/join/BitSetProducer;)V"


def flags(recipe):
    selected = selectors(recipe)
    if not selected:
        return []
    result = ["-Dupgrade.observe.actions=" + "|".join(selected.values())]
    optional = optional_constructor(recipe)
    if optional:
        result.append("-Dupgrade.observe.optional=" + optional)
    return result


def atom(text):
    if text == "null":
        return {"type": "null", "alias": None, "value": None}
    if not text.startswith("ref\t"):
        kind, raw = text.split("\t")
        return {"type": kind, "value": int(raw) if kind in {"int", "long"} else raw}
    _, identity, kind, value = text.split("\t", 3)
    if kind == "java.lang.String":
        value = decode(value).decode("utf-16-be", "surrogatepass")
    elif kind in {"java.util.Date", "java.lang.Long", "java.lang.Integer"}:
        value = int(value)
    elif kind == "java.time.Duration":
        seconds, nanos = map(int, value.split("/"))
        value = seconds * 1000 + nanos // 1_000_000
    elif kind == "org.apache.lucene.util.BytesRef":
        value = decode(value).decode("utf-8")
    elif kind == "org.apache.lucene.search.TopFieldDocs":
        total, *rows = decode(value).decode().splitlines()
        hits = []
        for row in rows:
            document, key = row.split("\t", 1)
            key = atom(key)
            if key["type"] not in {"null", "java.lang.Integer", "java.lang.Long", "org.apache.lucene.util.BytesRef", "java.lang.String"}:
                raise ValueError("no typed public sort-key observation for " + key["type"])
            hits.append([int(document), None if key["value"] is None else str(key["value"])])
        value = {"total": int(total), "hits": hits}
    else:
        value = None
    return {"type": kind, "alias": int(identity), "value": value}


def events(members, marks):
    by_member = {v:k for k,v in members.items()}
    actions = []
    for mark in marks:
        if not mark.startswith("UPGRADE-ACTION "):
            continue
        member, caller, pc, thread, loader, receiver, result, *args = decode(mark.split(" ", 1)[1]).decode().split("\n")
        role = by_member.get(member)
        if role is None and "callback" in members and member.startswith("UpgradeProbe#lambda$observe$"):
            role = "callback"
        if role is None:
            raise ValueError("unregistered public action " + member)
        actions.append({"role": role, "member": member, "caller": caller, "callerBci": int(pc),
                        "thread": int(thread), "loader": loader, "receiver": atom(receiver),
                        "return": atom(result), "args": [atom(a) for a in args]})
    if len({a["thread"] for a in actions}) != 1:
        raise ValueError("the registered synchronous history needs witnessed actions on one thread")
    return actions


def bindings(actions, loaded, files, hashes, feature, jdk, compiled):
    """Resolve the debugger's actual declarations through the providers loaded by this subject."""
    bound = {}
    for action in actions:
        member = action["member"]
        if member in bound:
            require(bound[member]["loader"] == action["loader"], "public action changed its defining loader")
            continue
        owner, method, descriptor = runtime_jar.parse_target(member)
        internal = runtime_jar.internal(owner)
        filename = internal + ".class"
        record = {"loader": action["loader"]}
        if action["loader"] == "bootstrap":
            module = jdk / "jmods/java.base.jmod"
            if module.is_file():
                with zipfile.ZipFile(module) as z:
                    data = z.read("classes/" + filename)
                record["provider"] = "java.base"
            else:
                with zipfile.ZipFile(jdk / "jre/lib/rt.jar") as z:
                    data = z.read(filename)
                record["provider"] = "jre/lib/rt.jar"
        else:
            origins = loaded.get(owner, set())
            require(len(origins) == 1, "unbound original action provider for " + member)
            provider, = origins
            if provider == compiled:
                require(internal.split("$")[0] == "UpgradeProbe", "unregistered generated action")
                data = (compiled / filename).read_bytes()
                record["provider"] = "compiled caller"
            else:
                require(provider in files, "public action was loaded outside the registered deployment")
                index = files.index(provider)
                record.update(providerIndex=index, artifactSha256=hashes[index])
                data = (provider/filename).read_bytes() if provider.is_dir() else runtime_jar.effective_class(provider, internal, feature)
        require(data and runtime_jar.this_class(data) == internal and (method, descriptor) in runtime_jar.methods(data),
                "the observed action is missing from its physical provider")
        bound[member] = {**record, "classSha256": hashlib.sha256(data).hexdigest()}
    return bound


def require(condition, message):
    if not condition:
        raise ValueError(message)


def copies(actions, inputs):
    copies = [a for a in actions if a["role"] == "copy"]
    require(len(copies) == 1, "history requires one original copy construction")
    original = copies[0]["args"][0]["alias"]
    copy = copies[0]["receiver"]["alias"]
    require(original is not None and copy != original, "the original and copy must be distinct objects")
    transfers = [a for a in actions if a["role"] == "copyTo"]
    require(len(transfers) == 1 and transfers[0]["receiver"]["alias"] == original, "copyTo used another message")
    after = actions[actions.index(transfers[0]) + 1:]
    mode = inputs["mode"]
    paired = mode == "paired mutations"
    mutations = [a for a in after if a["role"] == "mutate"]
    require([a["args"][0]["value"] for a in mutations] ==
            ([inputs[k] for k in ("mutateInput", "mutateReturn", "mutateTarget")] if paired else []),
            "the three date mutations must occur in registered order")
    if paired:
        setters = [a for a in actions if a["role"] == "set"]
        require(len(setters) == 1 and setters[0]["receiver"]["alias"] == original
                and setters[0]["args"][0]["alias"] == mutations[0]["receiver"]["alias"], "first mutation lost the supplied date")
    samples = []
    getters = []
    last_getter = None
    for step in after:
        role = step["role"]
        if role in {"get", "override"}:
            last_getter = step
        elif role == "sample":
            date = step["args"][0]
            require(step["return"]["value"] == date["value"], "sample disagrees with the actual retained date")
            if last_getter is not None:
                require(date["alias"] == last_getter["return"]["alias"], "sample used a different getter result")
                getters.append(last_getter["receiver"]["alias"])
            else:
                require(not paired and len(samples) == 2, "a public sample lost its getter")
            last_getter = None
            samples.append(date["value"])
        elif role == "mutate":
            require(len(samples) == mutations.index(step) * 2, "sample was taken on the wrong side of a mutation")
            if step == mutations[1]:
                require(last_getter and last_getter["receiver"]["alias"] == original and
                        last_getter["return"]["alias"] == step["receiver"]["alias"], "second mutation lost the returned date")
            last_getter = None
    require(getters == [original, copy] * (3 if paired else 1), "samples must alternate the original and its retained copy")
    require(len(samples) == (6 if paired else 3), "incomplete retained property history")
    if mode == "overridden getter":
        require(any(a["role"] == "override" for a in after), "getter-only override did not execute")
    return [samples[i:i+2] for i in range(0,6,2)] if paired else [samples]


def streams(actions, inputs):
    rows = []
    current = None
    for step in actions:
        role = step["role"]
        if role == "publisher":
            require(current is None, "a publisher was constructed without a completed subscription")
            current = {"chain": step["return"]["alias"], "stage": 0, "events": [], "partial": None, "terminal": None}
        elif current is not None:
            if role in {"next", "complete", "error", "recover", "block"}:
                stages = ["next", "complete", "error", "recover", "block"]
                require(role == stages[current["stage"]] and step["receiver"]["alias"] == current["chain"],
                        "subscription did not retain the publisher returned by the public operation")
                current["stage"] += 1
                if role != "block":
                    current["chain"] = step["return"]["alias"]
                else:
                    require(current["terminal"] is not None and current["partial"] is None, "missing public terminal or event read")
                    rows.append([current["events"], *current["terminal"]])
                    current = None
            elif role == "data":
                require(current["partial"] is None, "event data read without completing the preceding event")
                current["partial"] = [step["receiver"]["alias"], step["return"]["value"], None]
            elif role == "retry":
                require(current["partial"] and current["partial"][0] == step["receiver"]["alias"], "retry belongs to another event")
                current["partial"][2] = step["return"]["value"]
            elif role == "cause":
                current["cause"] = [step["receiver"]["alias"], step["return"]]
            elif role == "callback" and step["member"].endswith(")V"):
                if current["partial"] is not None:
                    event, value, retry = current["partial"]
                    require(step["args"][-1].get("alias") == event, "payload came from another callback")
                    current["events"].append([value, retry])
                    current["partial"] = None
                elif step["member"].endswith("Ljava/lang/Throwable;)V"):
                    error = step["args"][-1]
                    cause = current.get("cause")
                    require(cause and cause[0] == error["alias"], "error and cause lost their public identity")
                    current["terminal"] = ["error", error["type"], None if cause[1]["type"] == "null" else cause[1]["type"]]
                elif step["member"].endswith("([Ljava/lang/String;)V"):
                    current["terminal"] = ["complete", None, None]
    require(current is None and len(rows) == len(inputs["streams"]), "missing subscription of the original public publisher")
    return rows


def search(actions, inputs):
    setup = [a for a in actions if a["role"] in {"writer", "add", "close", "open", "searcher"}]
    required = ["writer", *(["add"] * len(inputs["blocks"])), "close", "open", "searcher"]
    require([a["role"] for a in setup] == required, "the parent/child index must be built, closed and reopened")
    writer, *adds, close, opened, searcher = setup
    require(all(a["receiver"]["alias"] == writer["receiver"]["alias"] for a in [*adds,close])
            and opened["args"][0]["alias"] == writer["args"][0]["alias"]
            and searcher["args"][0]["alias"] == opened["return"]["alias"], "search reopened a different directory or reader")
    rows = []
    hits = []
    stored = document = None
    for step in actions[actions.index(searcher)+1:]:
        role = step["role"]
        if role == "search":
            require(not hits and step["receiver"]["alias"] == searcher["receiver"]["alias"], "search lost its reader or ordered hits")
            result = step["return"]["value"]
            hits = list(result["hits"])
            rows.append([result["total"], []])
        elif role == "stored":
            require(step["receiver"]["alias"] == searcher["receiver"]["alias"], "stored fields came from another index")
            stored = step["return"]["alias"]
        elif role == "document":
            require(hits and stored == step["receiver"]["alias"] and hits[0][0] == step["args"][0]["value"],
                    "document read differs from the next actual ordered hit")
            document = step["return"]["alias"]
        elif role == "identifier":
            require(hits and document == step["receiver"]["alias"] and step["args"][0]["value"] == "identity",
                    "identifier read differs from the stored document")
            rows[-1][1].append([step["return"]["value"], hits.pop(0)[1]])
            document = stored = None
    require(not hits and rows, "missing ordered hits from the actual result")
    return rows


def qualify(recipe, inputs, marks, values):
    members = selectors(recipe)
    actions = events(members, marks)
    if "copy" in members:
        actual = copies(actions, inputs)
    elif "publisher" in members:
        actual = streams(actions, inputs)
    else:
        actual = search(actions, inputs)
        if inputs["childMissing"]:
            presence = {m.partition(" ")[2] for m in marks if m.startswith("UPGRADE-OPTIONAL ")}
            optional = optional_constructor(recipe)
            if presence == {optional + "\tfalse"}:
                require(len(actual) == 1, "unexpected queries with an absent original overload")
                actual.append(["overload-absent"])
            else:
                require(presence == {optional + "\ttrue"} and len(actual) == len(inputs["childMissing"]) + 1,
                        "missing original declaration or a registered sort query")
    require(actual == values, "reported projection differs from the independent actions, receivers or original return values")
    return actions
