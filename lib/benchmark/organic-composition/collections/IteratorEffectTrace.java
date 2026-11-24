import com.sun.jdi.*;
import com.sun.jdi.connect.Connector;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.*;

/** Check or substitute one updateCurrentIterator on the registered caller's actual objects. */
public final class IteratorEffectTrace {
    private static final String CHAIN = "org.apache.commons.collections4.iterators.IteratorChain";
    private static final String DECORATOR = "org.apache.commons.collections4.iterators.UnmodifiableIterator";
    private static final String OBSERVE = "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;";
    private final VirtualMachine vm;
    private final Path work;
    private final Path certificate;
    private final List<Long> returns;
    private IteratorHeap heap;
    private ObjectReference parent, child, mutable, sibling, decorator;
    private boolean throwSeen;
    private boolean completed, nextSeen, removeSeen, leafSeen;

    private IteratorEffectTrace(VirtualMachine vm, Path work, Path certificate, List<Long> returns) {
        this.vm = vm;
        this.work = work;
        this.certificate = certificate;
        this.returns = returns;
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }

    private static String member(Location at) {
        return at.declaringType().name() + "#" + at.method().name() + at.method().signature();
    }

    private static String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static void write(Path path, Map<String, String> data) throws Exception {
        List<String> lines = new ArrayList<>();
        new TreeMap<>(data).forEach((key, value) -> lines.add(key + "\t" + value));
        Files.write(path, lines);
    }

    private static Map<String, String> read(Path path) throws Exception {
        Map<String, String> result = new TreeMap<>();
        for (String line : Files.readAllLines(path)) {
            String[] pair = line.split("\t", -1);
            require(pair.length == 2 && result.put(pair[0], pair[1]) == null, "invalid certificate table");
        }
        return result;
    }

    private static Value field(ObjectReference object, String name) {
        Field slot = object.referenceType().fieldByName(name);
        require(slot != null && !slot.isStatic(), "missing instance field " + name);
        return object.getValue(slot);
    }

    private static ObjectReference ref(ObjectReference object, String name) {
        return (ObjectReference)field(object, name);
    }

    private void stopAt(Location location, String purpose) {
        BreakpointRequest point = vm.eventRequestManager().createBreakpointRequest(location);
        point.putProperty("purpose", purpose);
        point.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        point.enable();
    }

    private void install(ReferenceType type) {
        require(type.name().equals(CHAIN) && vm.classesByName(CHAIN).size() == 1, "ambiguous chain implementation");
        Method update = type.methodsByName("updateCurrentIterator", "()V").getFirst();
        stopAt(update.location(), "entry");
        for (long pc : returns) stopAt(update.locationOfCodeIndex(pc), "return");
        stopAt(type.methodsByName("next", "()Ljava/lang/Object;").getFirst().location(), "next");
        stopAt(type.methodsByName("remove", "()V").getFirst().location(), "remove");
    }

    private void resolveCacheField(BreakpointEvent hit, ObjectReference truth, Map<String, String> before) throws Exception {
        ReferenceType expected = truth.referenceType();
        Field cache = parent.referenceType().fieldByName("cachedHasNextValue");
        require(expected.name().equals("java.lang.Boolean") && expected.classLoader() == null
                && cache.signature().equals("Ljava/lang/Boolean;"), "unexpected cache field type");
        String action = "already resolved";
        try {
            require(cache.type().equals(expected), "different resolved cache field type");
        } catch (ClassNotLoadedException unresolved) {
            // JDI validates an assignment against the field owner's initiating loader. At this first
            // hasNext the bootstrap Boolean exists, but this loader may never have resolved its name.
            ClassType cls = (ClassType) vm.classesByName("java.lang.Class").getFirst();
            Method forName = cls.concreteMethodByName("forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;");
            ClassLoaderReference loader = cache.declaringType().classLoader();
            require(loader != null, "missing iterator class loader");
            Value resolved = cls.invokeMethod(hit.thread(), forName,
                    List.of(vm.mirrorOf(expected.name()), vm.mirrorOf(false), loader), ClassType.INVOKE_SINGLE_THREADED);
            require(expected.classObject().equals(resolved) && cache.type().equals(expected), "unresolved cache field type");
            action = "Class.forName with initialization disabled in the field owner's loader";
        }
        StackFrame resumed = hit.thread().frame(0);
        require(parent.equals(resumed.thisObject()) && resumed.location().equals(hit.location())
                && before.equals(heap.snapshot()), "type resolution changed the original helper entry");
        write(work.resolve("type-resolution.tsv"), Map.of("field", IteratorHeap.member(cache), "type", expected.name(),
                "loader", "bootstrap", "action", action, "entry", "same receiver, instruction and complete entry heap"));
    }

    private void start(BreakpointEvent hit, List<StackFrame> stack) throws Exception {
        StackFrame observer = stack.get(2);
        Map<String, ObjectReference> roots = new LinkedHashMap<>();
        for (String name : List.of("parent", "child", "backing", "tail")) {
            LocalVariable local = observer.visibleVariableByName(name);
            require(local != null, "missing original caller local " + name);
            roots.put(name, (ObjectReference)observer.getValue(local));
        }
        ReferenceType bool = vm.classesByName("java.lang.Boolean").getFirst();
        roots.put("Boolean.TRUE", (ObjectReference)bool.getValue(bool.fieldByName("TRUE")));
        parent = roots.get("parent");
        child = roots.get("child");
        require(parent.equals(stack.get(0).thisObject()) && parent.equals(stack.get(1).thisObject()), "wrong parent receiver");
        mutable = ref(child, "currentIterator");
        List<ObjectReference> boundaries = new ArrayList<>();
        if (mutable == null) {
            mutable = ref(ref(ref(child, "iteratorQueue"), "first"), "item");
            decorator = ref(ref(ref(parent, "iteratorQueue"), "first"), "item");
            require(decorator.referenceType().name().equals(DECORATOR), "unexpected unadvanced history");
            boundaries.add(decorator);
            ExceptionRequest exceptions = vm.eventRequestManager().createExceptionRequest(null, true, true);
            exceptions.addClassFilter(DECORATOR);
            exceptions.setSuspendPolicy(EventRequest.SUSPEND_ALL);
            exceptions.enable();
        }
        sibling = ref(ref(ref(parent, "iteratorQueue"), "last"), "item");
        boundaries.add(mutable);
        boundaries.add(sibling);
        for (ObjectReference leaf : boundaries) {
            Method remove = ((ClassType)leaf.referenceType()).concreteMethodByName("remove", "()V");
            stopAt(remove.location(), "leaf");
        }
        Map<String, String> sites = new TreeMap<>();
        for (int i = 0; i < 3; i++) {
            Location location = stack.get(i).location();
            String role = List.of("helper", "caller", "observer").get(i);
            require(vm.classesByName(location.declaringType().name()).size() == 1, "ambiguous live frame");
            sites.put(role, member(location));
            sites.put(role + ".pc", Long.toString(location.codeIndex()));
            sites.put(role + ".code", digest(location.method().bytecodes()));
            sites.put(role + ".pool", digest(location.declaringType().constantPool()));
        }
        write(work.resolve("sites.tsv"), sites);
        heap = new IteratorHeap(vm, roots);
        Map<String, String> before = heap.snapshot();
        write(work.resolve("before.tsv"), before);
        if (certificate == null) return;

        require(sites.equals(read(certificate.resolve("sites.tsv"))), "live call site differs");
        require(before.equals(read(certificate.resolve("before.tsv"))), "live prestate differs");
        if (decorator != null) resolveCacheField(hit, roots.get("Boolean.TRUE"), before);
        heap.apply(read(certificate.resolve("writes.tsv")));
        Map<String, String> after = heap.snapshot();
        require(after.equals(read(certificate.resolve("after.tsv"))), "substituted frame differs");
        write(work.resolve("after.tsv"), after);
        hit.thread().forceEarlyReturn(vm.mirrorOfVoid());
        Files.writeString(work.resolve("completion"), "substituted at bytecode entry");
        completed = true;
    }

    private void step(BreakpointEvent hit) throws Exception {
        String purpose = (String)hit.request().getProperty("purpose");
        List<StackFrame> stack = hit.thread().frames();
        ObjectReference receiver = stack.getFirst().thisObject();
        if (purpose.equals("entry") || purpose.equals("return")) {
            if (stack.size() < 3 || !member(stack.get(1).location()).equals(CHAIN + "#hasNext()Z")
                    || !member(stack.get(2).location()).equals(OBSERVE)) return;
            if (purpose.equals("entry") && heap == null) start(hit, stack);
            else if (purpose.equals("return") && !completed && heap != null && receiver.equals(parent)) {
                write(work.resolve("after.tsv"), heap.snapshot());
                Files.writeString(work.resolve("completion"), "original return at " + hit.location().codeIndex());
                completed = true;
            }
            return;
        }
        if (!completed) return;
        if (purpose.equals("leaf")) {
            if (!removeSeen || (!receiver.equals(mutable) && !receiver.equals(sibling) && !receiver.equals(decorator))) return;
            // The leaf must be removing on behalf of this very parent, called directly by the observer.
            for (int i = 1; i + 1 < stack.size(); i++) {
                if (member(stack.get(i).location()).equals(CHAIN + "#remove()V")
                        && parent.equals(stack.get(i).thisObject()) && member(stack.get(i + 1).location()).equals(OBSERVE)) {
                    require(!leafSeen, "multiple removal boundaries");
                    Map<String,String> fields = new TreeMap<>(Map.of("receiver", heap.label(receiver),
                            "member", member(hit.location()), "caller", member(stack.get(1).location())));
                    if (decorator != null) {
                        require(receiver.equals(decorator) && i == 1, "removal bypassed the selected decorator");
                        fields.put("delegate", heap.label(field(receiver, "iterator")));
                    }
                    write(work.resolve("leaf.tsv"), fields);
                    leafSeen = true;
                    return;
                }
            }
            return;
        }
        if (!receiver.equals(parent) || !member(stack.get(1).location()).equals(OBSERVE)) return;
        if (purpose.equals("next") && !nextSeen) {
            write(work.resolve("next.tsv"), Map.of("site", Long.toString(stack.get(1).location().codeIndex()),
                    "current", heap.label(field(parent, "currentIterator"))));
            nextSeen = true;
        } else if (purpose.equals("remove") && !removeSeen) {
            require(nextSeen, "parent remove preceded the registered next");
            Map<String,String> fields = new TreeMap<>(Map.of("site", Long.toString(stack.get(1).location().codeIndex()),
                    "lastUsed", heap.label(field(parent, "lastUsedIterator")), "childLastUsed", heap.label(field(child, "lastUsedIterator")),
                    "mutableCursor", field(mutable, "cursor").toString(), "siblingCursor", field(sibling, "cursor").toString()));
            if (decorator != null) fields.put("childLocked", field(child, "isLocked").toString());
            write(work.resolve("remove.tsv"), fields);
            removeSeen = true;
        }
    }

    private void throwing(ExceptionEvent event) throws Exception {
        require(leafSeen && !throwSeen && event.catchLocation() != null, "unexpected decorator exception");
        List<StackFrame> stack = event.thread().frames();
        require(decorator.equals(stack.get(0).thisObject()) && parent.equals(stack.get(1).thisObject())
                && member(stack.get(1).location()).equals(CHAIN + "#remove()V")
                && member(stack.get(2).location()).equals(OBSERVE), "wrong exception call chain");
        Location location = event.location();
        write(work.resolve("throw.tsv"), Map.ofEntries(
                Map.entry("receiver", heap.label(stack.get(0).thisObject())), Map.entry("from", member(location)),
                Map.entry("at", Long.toString(location.codeIndex())), Map.entry("code", digest(location.method().bytecodes())),
                Map.entry("pool", digest(location.declaringType().constantPool())),
                Map.entry("type", event.exception().referenceType().name()), Map.entry("caughtBy", member(event.catchLocation())),
                Map.entry("caughtAt", Long.toString(event.catchLocation().codeIndex())),
                Map.entry("parentCall", Long.toString(stack.get(1).location().codeIndex())),
                Map.entry("parentCode", digest(stack.get(1).location().method().bytecodes()))));
        throwSeen = true;
    }

    private void run() throws Exception {
        ClassPrepareRequest prepare = vm.eventRequestManager().createClassPrepareRequest();
        prepare.addClassFilter(CHAIN);
        prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        prepare.enable();
        try {
            boolean done = false;
            while (!done) {
                EventSet batch = vm.eventQueue().remove();
                for (Event event : batch) {
                    if (event instanceof ClassPrepareEvent loaded) install(loaded.referenceType());
                    else if (event instanceof BreakpointEvent point) step(point);
                    else if (event instanceof ExceptionEvent thrown) throwing(thrown);
                    else if (event instanceof VMDisconnectEvent) done = true;
                }
                if (!done) batch.resume();
            }
        } catch (VMDisconnectedException ended) {
            // The VM may close the event connection immediately after VMDeath.
        }
        require(completed && nextSeen && removeSeen && leafSeen, "incomplete original public continuation");
        require(decorator == null || throwSeen, "the registered decorator did not throw");
    }

    private static String quoted(String value) {
        if (value.contains("\"")) throw new IllegalArgumentException("quote in launcher argument");
        return "\"" + value + "\"";
    }

    public static void main(String[] args) throws Exception {
        Path work = Path.of(args[0]);
        Path certificate = args[1].equals("-") ? null : Path.of(args[1]);
        List<Long> returns = Arrays.stream(args[2].split(",")).map(Long::parseLong).toList();
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        Map<String, Connector.Argument> launch = connector.defaultArguments();
        launch.get("home").setValue(System.getProperty("java.home"));
        launch.get("options").setValue("-Xmx384m -Duser.timezone=UTC -Duser.language=en -Duser.country=US "
                + quoted("-Djava.io.tmpdir=" + work) + " " + quoted("-Duser.home=" + work) + " "
                + quoted("-Dupgrade.observation.file=" + work.resolve("observation.txt")) + " -verbose:class -cp " + quoted(args[3]));
        launch.get("main").setValue("UpgradeObservation UpgradeProbe " + args[4]);
        VirtualMachine vm = connector.launch(launch);
        Process process = vm.process();
        Files.writeString(work.resolve("pid"), Long.toString(process.pid()));
        try (var stdout = Files.newOutputStream(work.resolve("classes.log"));
             var stderr = Files.newOutputStream(work.resolve("child.stderr"))) {
            var out = Thread.startVirtualThread(() -> pump(process.getInputStream(), stdout));
            var err = Thread.startVirtualThread(() -> pump(process.getErrorStream(), stderr));
            try {
                new IteratorEffectTrace(vm, work, certificate, returns).run();
                require(process.waitFor() == 0, "original JVM failed");
            } finally {
                if (process.isAlive()) process.destroyForcibly();
                out.join();
                err.join();
            }
        }
    }

    private static void pump(java.io.InputStream source, java.io.OutputStream dest) {
        try (source) { source.transferTo(dest); }
        catch (java.io.IOException e) { throw new java.io.UncheckedIOException(e); }
    }
}
