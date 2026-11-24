"""The independently specified heap effect for the pre-advanced IteratorChain history."""
import hashlib
import json

CHAIN = "org.apache.commons.collections4.iterators.IteratorChain"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EntryHeap:
    def __init__(self, state):
        self.state = state
        self.writes = {}

    def slot(self, owner, field):
        prefix = owner + "/"
        (key,) = (k for k in self.state if k.startswith(prefix) and "#" + field + ":" in k)
        return key

    def get(self, owner, field):
        return self.state[self.slot(owner, field)]

    def expect(self, owner, **fields):
        for name, value in fields.items():
            require(self.get(owner, name) == value, f"wrong prestate at {owner}.{name}")

    def set(self, owner, **fields):
        for name, value in fields.items():
            key = self.slot(owner, name)
            if self.state[key] != value:
                self.writes[key] = value


def declared_effect(state, layout):
    heap = EntryHeap(state)
    parent, child, backing, tail, truth = (state["root/" + n] for n in ("parent", "child", "backing", "tail", "Boolean.TRUE"))
    require(len({parent, child, backing, tail, truth}) == 5, "aliased caller roots")
    queue = heap.get(parent, "iteratorQueue")
    child_queue = heap.get(child, "iteratorQueue")
    mutable = heap.get(child, "currentIterator")
    first = heap.get(queue, "first")
    last = heap.get(queue, "last")
    sibling = heap.get(last, "item")
    retained = layout == "retained child"
    require(retained or layout == "flattened child", "unknown endpoint layout")
    selected = child if retained else sibling
    types = {parent: CHAIN, child: CHAIN, queue: "java.util.LinkedList", child_queue: "java.util.LinkedList",
             mutable: "java.util.ArrayList$Itr", sibling: "java.util.Arrays$ArrayItr", backing: "java.util.ArrayList",
             tail: "java.util.Arrays$ArrayList", first: "java.util.LinkedList$Node", truth: "java.lang.Boolean"}
    require(len(types) == 10 and all(state[ref + "/type"] == name for ref, name in types.items()),
            "caller roots or dynamic iterator types differ")
    heap.expect(parent, isLocked="Z:true", currentIterator="null", cachedHasNextValue="null", lastUsedIterator="null")
    heap.expect(child, isLocked="Z:true", cachedHasNextValue="null", lastUsedIterator=mutable)
    heap.expect(child_queue, size="I:0", first="null", last="null")
    heap.expect(mutable, cursor="I:1", lastRet="I:0", **{"this$0": backing})
    heap.expect(backing, size="I:3")
    heap.expect(sibling, cursor="I:0", a=heap.get(tail, "a"))
    heap.expect(truth, value="Z:true")
    heap.expect(first, item=selected, prev="null")
    successor = heap.get(first, "next")
    if retained:
        require(last != first and successor == last and state[last + "/type"] == "java.util.LinkedList$Node",
                "missing fixed-size sibling after the child")
        heap.expect(last, prev=first, next="null")
        heap.expect(queue, size="I:2")
        heap.set(last, prev="null")
        heap.set(child, cachedHasNextValue=truth)
    else:
        require(first == last and successor == "null", "unexpected flattened queue")
        heap.expect(queue, size="I:1")
        heap.set(queue, last="null")
    # LinkedList.unlinkFirst clears the detached node even if the caller cannot reach it afterward.
    mod_count = int(heap.get(queue, "modCount").removeprefix("I:"))
    require(0 <= mod_count < 2**31 - 1, "queue mutation count outside the registered history")
    heap.set(queue, first=successor, size="I:1" if retained else "I:0", modCount=f"I:{mod_count + 1}")
    heap.set(first, item="null", next="null")
    heap.set(parent, currentIterator=selected, cachedHasNextValue=truth)
    return heap.writes, {"parent": parent, "child": child, "selected": selected, "mutable": mutable,
                         "sibling": sibling, "queue": queue, "detached": first}


def check_continuation(trial, roles, binding):
    retained = binding["layout"] == "retained child"
    require(trial["observation"] == binding["originalObservation"], "public observation differs")
    require(trial["next"] == {"current": roles["selected"], "site": str(binding["publicNextSite"])},
            "the original next site lost the selected iterator")
    remove = trial["remove"]
    require(remove["lastUsed"] == roles["selected"] and remove["childLastUsed"] == roles["mutable"],
            "wrong receiver for the parent or child removal")
    require((remove["mutableCursor"], remove["siblingCursor"]) == (("2", "0") if retained else ("1", "1")),
            "wrong leaf cursor at parent.remove")
    leaf = trial["leaf"]
    expected_leaf = "java.util.ArrayList$Itr" if retained else "java.util.Iterator"
    require(leaf["receiver"] == roles["mutable" if retained else "sibling"]
            and leaf["member"] == expected_leaf + "#remove()V" and leaf["caller"] == CHAIN + "#remove()V",
            "underlying remove dispatch differs")


def certify(binding, before, sites, originals, proposal):
    writes, roles = declared_effect(before, binding["layout"])
    require(writes == proposal, "proposed writes differ from the declared effect")
    require(len(originals) == 2 and len({t["pid"] for t in originals}) == 2, "two fresh originals required")
    expected = {"before": digest(before), "after": digest(before | writes), "sites": digest(sites)}
    normal = {f"original return at {pc}" for pc in binding["returnBCIs"]}
    for trial in originals:
        require(trial["completion"] in normal, "missing original normal return")
        require(all(trial[k] == v for k, v in expected.items()), "original heap or call site differs")
        check_continuation(trial, roles, binding)
    evidence = {"binding": digest(binding), **expected, "writes": digest(writes), "originals": digest(originals)}
    return digest(evidence)


def admit(certificate, binding, before, sites, originals, writes):
    require(certificate == certify(binding, before, sites, originals, writes),
            "certificate belongs to a different deployment or execution")
