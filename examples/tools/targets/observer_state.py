"""Stateful public reads on retained views, synchronous listeners and mutable maps."""
import re
from targets import runtime_jar
from targets.observer_recipes import keys, nonempty, Unsupported

WEIGHTS = ["write.outcome", "view.weight", "backing.weight"]
TRANSITIONS = ["command.outcome", "state", "listener.count", "listener.events"]
MAP = ["remove.flags", "remaining.mappings", "retained.keys", "null.key"]


def select(entry, fields, inputs, api):
    owner, method, descriptor = runtime_jar.parse_target(entry)
    package = owner.rpartition(".")[0]
    recipe = {"owner": owner, "method": method}
    if fields == WEIGHTS:
        api.require(owner, method, "(Ljava/lang/Object;D)V")
        api.require(owner, "getEdgeWeight", "(Ljava/lang/Object;)D")
        _, ctor = api.select(owner, ["<init>"], r"\(L[\w/$]+;Ljava/util/function/Function;ZZ\)V")
        base = ctor[2:].split(";")[0].replace("/", ".")
        backing, edge = package + ".SimpleWeightedGraph", package + ".DefaultWeightedEdge"
        api.require(backing, "<init>", "(Ljava/lang/Class;)V")
        api.require(edge, "<init>", "()V")
        api.require(base, "addVertex", "(Ljava/lang/Object;)Z")
        api.require(base, "addEdge", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;")
        for item in inputs:
            keys(item, ["assertions", "cache", "through", "backingWeight", "viewWeight", "writes"])
            if (any(type(item[k]) != bool for k in ("assertions","cache","through")) or
                    any(type(x) != int for x in [item["backingWeight"], item["viewWeight"], *nonempty(item["writes"], "weight updates")])):
                raise Unsupported("weight view needs concrete options, initial weights and updates")
        return {**recipe, "family": "weight view and backing graph", "base": base, "backing": backing, "edge": edge,
                "publicReader": owner + "#getEdgeWeight(Ljava/lang/Object;)D"}
    if fields == TRANSITIONS:
        api.require(owner, method, "()V")
        interfaces = [i.replace("/", ".") for i in runtime_jar.interfaces(api.definition(owner))]
        roots = [i for i in interfaces if (method, "()V") in runtime_jar.methods(api.definition(i))]
        if len(roots) != 1:
            raise Unsupported("need one public command interface with the registered transition")
        interface, = roots
        api.require(interface, "ofDefaults", "(Ljava/lang/String;)L" + runtime_jar.internal(interface) + ";", static=True)
        _, publisher = api.select(interface, ["getEventPublisher"], r"\(\)L[\w/$]+;")
        pub = publisher[3:-1].replace("/", ".")
        api.select(pub, ["onStateTransition"], r"\(L[\w/$]+;\)L" + re.escape(runtime_jar.internal(pub)) + ";")
        commands = {}
        for (name, desc) in runtime_jar.methods(api.definition(interface)):
            m = re.fullmatch(r"transitionTo(\w+)State", name)
            if m and desc == "()V":
                label = re.sub(r"(?<!^)(?=[A-Z])", "_", m[1]).upper()
                commands[label] = name
        for item in inputs:
            keys(item, ["states"])
            if any(s not in commands for s in nonempty(item["states"], "state command sequence")):
                raise Unsupported("missing public transition for a registered state")
        return {**recipe, "family": "commands on one listener-backed state machine", "interface": interface,
                "commands": dict(sorted(commands.items())), "invocationVia": interface + "#" + method + "()V"}
    if fields == MAP:
        api.require(owner, method, descriptor)
        api.require(owner, "<init>", "()V")
        if not re.fullmatch(r"\(L[\w/$]+;\)Z", descriptor):
            raise Unsupported("need a boolean-returning map removal with a binary predicate")
        for item in inputs:
            keys(item, ["maximumSize", "reverse", "nullValue"])
            if not 0 <= item["maximumSize"] <= 8 or type(item["reverse"]) != bool or type(item["nullValue"]) != int:
                raise Unsupported("need a bounded collision domain and a two-argument removal predicate")
        return {**recipe, "family": "collision subsets on a live map view"}
    raise Unsupported("unsupported retained-state history")


def body(p):
    if p["family"] == "weight view and backing graph":
        body = '''
            ClassLoader loader = OWNER.class.getClassLoader();
            loader.setClassAssertionStatus(OWNER.class.getName(), (Boolean)data.get("assertions"));
            BASE<String,EDGE> backing = new BACKING<>(EDGE.class);
            backing.addVertex("left");
            backing.addVertex("right");
            EDGE edge = backing.addEdge("left", "right");
            backing.setEdgeWeight(edge, ((Number)data.get("backingWeight")).doubleValue());
            OWNER<String,EDGE> view = new OWNER<>(backing,
                    e -> ((Number)data.get("viewWeight")).doubleValue(), (Boolean)data.get("cache"), (Boolean)data.get("through"));
            for (Integer weight : (List<Integer>)data.get("writes")) {
                String completion;
                try {
                    view.METHOD(edge, weight.doubleValue());
                    completion = "returned";
                } catch (RuntimeException | AssertionError error) { completion = error.getClass().getSimpleName(); }
                observations.add(row(completion, view.getEdgeWeight(edge), backing.getEdgeWeight(edge)));
            }'''
        for name in ("owner", "base", "backing", "edge", "method"):
            body = body.replace(name.upper(), p[name])
        return body, ""
    if p["family"] == "commands on one listener-backed state machine":
        cases = "\n".join('case "' + state + '": receiver.' + name + '(); break;' for state,name in p["commands"].items())
        body = '''
            INTERFACE receiver = INTERFACE.ofDefaults("observation");
            List<String> events = new ArrayList<>();
            receiver.getEventPublisher().onStateTransition(event -> events.add(event.getStateTransition().name()));
            for (String state : (List<String>)data.get("states")) {
                String completion;
                try {
                    switch (state) {
                        CASES
                        default: throw new IllegalArgumentException("unknown transition");
                    }
                    completion = "returned";
                } catch (RuntimeException error) { completion = error.getClass().getSimpleName(); }
                observations.add(row(completion, receiver.getState().name(), events.size()));
            }
            observations.add(new ArrayList<>(events));'''
        return body.replace("INTERFACE", p["interface"]).replace("CASES", cases), ""
    body = '''
        int maximum = (Integer)data.get("maximumSize");
        boolean reverse = (Boolean)data.get("reverse");
        for (int count=0; count<=maximum; count++) for (int subset=0; subset<(1<<count); subset++) {
            final int mask = subset;
            OWNER<Key,Integer> map = new OWNER<>();
            Key[] keys = new Key[count];
            for (int n=0; n<count; n++) {
                int k = reverse ? count-n-1 : n;
                keys[k] = new Key(k);
                map.put(keys[k], k);
            }
            map.put(null, (Integer)data.get("nullValue"));
            Set<Key> view = map.keySet();
            List<Object> steps = new ArrayList<>();
            for (int call=0; call<2; call++) {
                boolean removed = map.METHOD((key, value) -> key != null && (mask & (1<<key.id)) != 0);
                List<Object> mappings = new ArrayList<>(), retained = new ArrayList<>();
                for (int k=0; k<count; k++) {
                    if (map.containsKey(keys[k])) mappings.add(row(k, map.get(keys[k])));
                    if (view.contains(keys[k])) retained.add(k);
                }
                steps.add(row(removed, mappings, retained, map.size(), view.contains(null), map.get(null)));
            }
            observations.add(row(count, mask, steps));
        }'''.replace("OWNER", p["owner"]).replace("METHOD", p["method"])
    support = '''
        private static final class Key {
            final int id;
            Key(int id) { this.id = id; }
            public int hashCode() { return 1; }
            public boolean equals(Object other) { return other instanceof Key && ((Key)other).id == id; }
        }'''
    return body, support
