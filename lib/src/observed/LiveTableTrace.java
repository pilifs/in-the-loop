import com.sun.jdi.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.util.*;

/** Read the unchanged System.props object through JDI. Only the keys' and values'
 * digests leave the VM pair. An unrepresented view, write or alias ends admission. */
final class LiveTableTrace {
    private final VirtualMachine vm;
    private final EventRequestManager req;
    private final List<EventRequest> requests = new ArrayList<>();
    private final List<String> events;
    private ThreadReference thread;
    private ObjectReference table;
    private Set<Long> before;
    private String projection;
    private ObjectReference callback;
    private BreakpointRequest visit;
    private MethodExitRequest returned;
    private String operation, caller;
    private int depth;
    private final List<byte[]> pairs = new ArrayList<>();
    private final Map<String, Integer> reads = new TreeMap<>();
    private final Map<String,Value> own = new HashMap<>();
    private final Map<EventRequest,KeyRead> keyed = new HashMap<>();
    private record KeyRead(String name,String descriptor,String key,String caller,int depth,Value expected,boolean booleanResult,boolean present) {}

    LiveTableTrace(VirtualMachine vm, List<String> events) {
        this.vm = vm; this.req = vm.eventRequestManager(); this.events = events;
    }

    private static String q(String s) { return ObservedInitializer.text(s); }
    private void enable(EventRequest r) {
        r.putProperty("liveTable", true);
        r.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
        r.enable(); requests.add(r);
    }

    private Set<Long> references() {
        Set<Long> refs = new HashSet<>();
        for (ObjectReference o : table.referringObjects(257)) refs.add(o.uniqueID());
        if (refs.size() > 256) throw new IllegalStateException("system table alias bound exceeded");
        return refs;
    }

    private static Value field(ObjectReference object, String name) {
        return object.getValue(Objects.requireNonNull(object.referenceType().fieldByName(name), "missing table field " + name));
    }

    private String projection() throws Exception {
        ObjectReference map = (ObjectReference) field(table, "map");
        if (!map.referenceType().name().equals("java.util.concurrent.ConcurrentHashMap") || map.referenceType().classLoader() != null)
            throw new IllegalStateException("unrecognized JDK Properties backing table");
        ArrayReference buckets = (ArrayReference) field(map, "table");
        List<byte[]> entries = new ArrayList<>();
        Set<Long> seen = new HashSet<>();
        int hash = 0;
        if (buckets != null) for (Value bucket : buckets.getValues()) {
            ObjectReference node = (ObjectReference) bucket;
            if (node != null && node.referenceType().name().endsWith("$TreeBin")) node = (ObjectReference) field(node, "first");
            while (node != null) {
                if (!Set.of("java.util.concurrent.ConcurrentHashMap$Node","java.util.concurrent.ConcurrentHashMap$TreeNode").contains(node.referenceType().name())
                        || !seen.add(node.uniqueID()) || entries.size() >= 16384)
                    throw new IllegalStateException("unrepresented or changing JDK Properties table shape");
                if (!(field(node,"key") instanceof StringReference key) || !(field(node,"val") instanceof StringReference value))
                    throw new IllegalStateException("non-string system property key or value");
                own.put(key.value(),value);
                entries.add(ObservedInitializer.tablePair(key.value(), value.value()));
                hash += key.value().hashCode() ^ value.value().hashCode();
                node = (ObjectReference) field(node,"next");
            }
        }
        String order = ObservedInitializer.tableDigest(entries);
        entries.sort(Arrays::compareUnsigned);
        return "{\"type\":\"java.util.Properties\",\"count\":" + entries.size() + ",\"orderSha256\":" + q(order)
                + ",\"entriesSha256\":" + q(ObservedInitializer.tableDigest(entries)) + ",\"hashCode\":" + hash + "}";
    }

    void begin(ThreadReference root) throws Exception {
        thread = root;
        if (!vm.canUseInstanceFilters() || !vm.canGetInstanceInfo() || !vm.canWatchFieldModification())
            throw new IllegalStateException("JDI cannot identify the original system-properties table and its aliases");
        ReferenceType system = vm.classesByName("java.lang.System").get(0);
        Field installed = system.fieldByName("props");
        table = (ObjectReference) system.getValue(installed);
        ReferenceType type = table.referenceType();
        if (!type.name().equals("java.util.Properties") || type.classLoader() != null)
            throw new IllegalStateException("custom live system-properties table");
        if (table.getValue(type.fieldByName("defaults")) != null)
            throw new IllegalStateException("live system-properties table has inherited defaults");
        projection = projection();
        before = references();
        MethodEntryRequest entry = req.createMethodEntryRequest();
        entry.addInstanceFilter(table);
        entry.addClassFilter(type);
        enable(entry);
        enable(req.createModificationWatchpointRequest(installed));
    }

    private static String site(StackFrame f) {
        Location l = f.location();
        return l.declaringType().name() + "#" + l.method().name() + l.method().signature() + "@" + l.codeIndex();
    }

    private String applicationCaller() throws Exception {
        for (StackFrame f : thread.frames().subList(1, thread.frameCount())) {
            if (f.location().declaringType().classLoader() != null) return site(f);
            if (!Set.of("java.lang.System","java.lang.Integer","java.lang.Long","java.lang.Boolean").contains(f.location().declaringType().name())) break;
        }
        return null;
    }

    private void keyEntry(Method m) throws Exception {
        String caller = applicationCaller();
        if (caller == null) return;
        var args = thread.frame(0).getArgumentValues();
        if (args.isEmpty()) return;
        if (!(args.get(0) instanceof StringReference key)) throw new IllegalStateException("non-string live property lookup");
        String name = key.value();
        boolean present = own.containsKey(name);
        Value expected = present ? own.get(name) : args.size()==2 ? args.get(1) : null;
        MethodExitRequest exit = req.createMethodExitRequest();
        exit.addClassFilter(m.declaringType());exit.addThreadFilter(thread); enable(exit);
        keyed.put(exit,new KeyRead(m.name(),m.signature(),name,caller,thread.frameCount(),expected,m.name().equals("containsKey"),present));
    }

    private void keyReturned(MethodExitEvent exit, KeyRead read) throws Exception {
        if (!exit.method().name().equals(read.name()) || !exit.method().signature().equals(read.descriptor()) || thread.frameCount()!=read.depth()) return;
        Value v=exit.returnValue();
        if (read.booleanResult() ? !(v instanceof BooleanValue b) || b.booleanValue()!=read.present() : !Objects.equals(v,read.expected()))
            throw new IllegalStateException("live property read disagrees with original membership or value identity at "+read.caller());
        String key=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(read.key().getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        String result=v instanceof StringReference s ? q(HexFormat.of().formatHex(ObservedInitializer.tablePair("",s.value())))
                : v==null ? "null" : read.booleanResult() ? Boolean.toString(read.present()) : q(v.type().signature());
        events.add("{\"operation\":"+q(read.name()+read.descriptor())+",\"caller\":"+q(read.caller())
                +",\"keySha256\":"+q(key)+",\"present\":"+read.present()+",\"resultProjection\":"+result+"}");
        req.deleteEventRequest(exit.request());requests.remove(exit.request());keyed.remove(exit.request());
    }

    boolean handle(Event e) throws Exception {
        if (e.request() == null || !Boolean.TRUE.equals(e.request().getProperty("liveTable"))) return false;
        if (!(e instanceof LocatableEvent l) || !l.thread().equals(thread))
            throw new IllegalStateException("another thread accessed the live properties table");
        if (e instanceof ModificationWatchpointEvent) throw new IllegalStateException("System.props was replaced inside the boundary");
        if (e instanceof BreakpointEvent) {
            StackFrame frame = thread.frame(0);
            if (!callback.equals(frame.thisObject())) throw new IllegalStateException("incorrect forEach callback identity");
            List<Value> args = frame.getArgumentValues();
            if (!(args.get(0) instanceof StringReference k) || !(args.get(1) instanceof StringReference v))
                throw new IllegalStateException("non-string system property key or value");
            if (pairs.size() >= 16384) throw new IllegalStateException("live table exceeds event bound");
            pairs.add(ObservedInitializer.tablePair(k.value(), v.value()));
        } else if (e instanceof MethodEntryEvent entry) {
            Method m = entry.method();
            if (!table.equals(thread.frame(0).thisObject())) throw new IllegalStateException("wrong live table receiver");
            String name = m.name();
            if (Set.of("getProperty","get","getOrDefault","containsKey","size","isEmpty").contains(name)) {
                reads.merge(name, 1, Integer::sum);
                keyEntry(m);
                return true;
            }
            String where = site(thread.frame(1));
            if (!(name.equals("forEach") || name.equals("hashCode")) || operation != null)
                throw new IllegalStateException("unrepresented live system-properties operation " + name + m.signature() + " at " + where);
            operation = name + m.signature(); caller = where; depth = thread.frameCount();
            returned = req.createMethodExitRequest();
            returned.addClassFilter(m.declaringType()); returned.addThreadFilter(thread);
            enable(returned);
            if (name.equals("forEach")) {
                callback = (ObjectReference) thread.frame(0).getArgumentValues().get(0);
                Method accept = callback.referenceType().methodsByName("accept","(Ljava/lang/Object;Ljava/lang/Object;)V").get(0);
                visit = req.createBreakpointRequest(accept.location());
                visit.addInstanceFilter(callback);
                enable(visit);
                pairs.clear();
            }
        } else if (e instanceof MethodExitEvent exit && keyed.containsKey(exit.request())) {
            keyReturned(exit,keyed.get(exit.request()));
        } else if (e instanceof MethodExitEvent exit && returned == exit.request()
                && (exit.method().name() + exit.method().signature()).equals(operation) && thread.frameCount() == depth) {
            String result;
            if (visit != null) {
                result = ",\"count\":" + pairs.size() + ",\"orderSha256\":" + q(ObservedInitializer.tableDigest(pairs));
                List<byte[]> sorted = new ArrayList<>(pairs);
                sorted.sort(Arrays::compareUnsigned);
                result += ",\"entriesSha256\":" + q(ObservedInitializer.tableDigest(sorted));
                req.deleteEventRequest(visit); requests.remove(visit); visit = null; callback = null;
            } else result = ",\"hashCode\":" + ((IntegerValue) exit.returnValue()).value();
            events.add("{\"operation\":" + q(operation) + ",\"caller\":" + q(caller) + result + "}");
            req.deleteEventRequest(returned); requests.remove(returned); returned = null; operation = null;
        }
        return true;
    }

    void finish() throws Exception {
        if (operation != null || !keyed.isEmpty()) throw new IllegalStateException("live system-properties read did not finish");
        Set<Long> after = references();
        after.removeAll(before);
        if (!after.isEmpty()) throw new IllegalStateException("a new reference to the live system-properties table escaped the boundary");
        if (!projection.equals(projection())) throw new IllegalStateException("live system table changed inside observation");
        req.deleteEventRequests(requests);
        events.add("{\"operation\":\"table boundary\",\"type\":\"java.util.Properties\",\"defaults\":null,\"newRetainedReferences\":0,\"keyedReads\":"
                + reads.values().stream().mapToInt(Integer::intValue).sum() + ",\"projection\":" + projection + "}");
    }
}
