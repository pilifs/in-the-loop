import com.sun.jdi.Bootstrap;
import com.sun.jdi.Field;
import com.sun.jdi.Location;
import com.sun.jdi.Method;
import com.sun.jdi.ObjectReference;
import com.sun.jdi.ReferenceType;
import com.sun.jdi.StackFrame;
import com.sun.jdi.VirtualMachine;
import com.sun.jdi.Value;
import com.sun.jdi.VMDisconnectedException;
import com.sun.jdi.connect.Connector;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.HashSet;
import java.util.Set;

/** Observe an actual entry in the child JVM launched here. The class files on its classpath are untouched. */
public final class UpgradeTrace {
    private static final boolean receivers = Boolean.getBoolean("upgrade.trace.receivers");

    private static final List<String> changed = Arrays.asList(System.getProperty("upgrade.trace.changed", "").split("\\|"));

    private static void changedBreakpoints(VirtualMachine vm, ReferenceType type) {
        for (String target : changed) {
            int hash = target.indexOf('#');
            if (hash < 0 || !type.name().equals(target.substring(0, hash))) continue;
            int desc = target.indexOf('(', hash);
            breakpoint(vm, type, target.substring(hash + 1, desc), target.substring(desc), "changed");
        }
    }

    // Emit metadata and within-frame aliases only. JDI reads slots without calling methods in the child.
    private static String shape(Value value, Map<Long, Integer> aliases) {
        if (value == null) return "null";
        if (!(value instanceof ObjectReference)) return value.type().signature();
        ObjectReference object = (ObjectReference) value;
        long id = object.uniqueID();
        if (!aliases.containsKey(id)) aliases.put(id, aliases.size());
        return object.referenceType().signature() + "@" + aliases.get(id);
    }

    private static String frameShape(StackFrame frame, boolean fields) {
        Map<Long, Integer> aliases = new LinkedHashMap<>();
        List<String> lines = new ArrayList<>();
        ObjectReference receiver = frame.thisObject();
        lines.add("this\t" + shape(receiver, aliases));
        for (Value arg : frame.getArgumentValues()) lines.add("arg\t" + shape(arg, aliases));
        if (fields && receiver != null) {
            List<Field> declared = new ArrayList<>(receiver.referenceType().allFields());
            declared.removeIf(Field::isStatic);
            declared.sort(Comparator.comparing(f -> f.declaringType().name() + "#" + f.name() + ":" + f.signature()));
            Map<Field, Value> values = receiver.getValues(declared);
            for (Field f : declared) lines.add("field\t" + f.declaringType().name() + "#" + f.name() + ":"
                    + f.signature() + "\t" + shape(values.get(f), aliases));
        }
        return String.join("\n", lines);
    }

    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }
    private static Thread forward(InputStream input, OutputStream output) {
        Thread thread = new Thread(() -> {
            try {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        });
        thread.start();
        return thread;
    }

    private static String quote(String value) {
        if (value.contains("\"")) throw new IllegalArgumentException("unrepresentable launcher argument");
        return "\"" + value + "\"";
    }

    private static void breakpoint(VirtualMachine vm, ReferenceType type, String name, String descriptor, String purpose) {
        for (Method method : type.methodsByName(name, descriptor)) {
            if (!method.declaringType().equals(type) || method.isAbstract() || method.isNative()) continue;
            BreakpointRequest point = vm.eventRequestManager().createBreakpointRequest(method.location());
            point.putProperty("purpose", purpose);
            point.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            point.enable();
        }
    }

    private static void install(VirtualMachine vm, ReferenceType type, String owner, String method,
                                String descriptor, Set<String> exceptions) {
        if (type.name().equals(owner)) {
            breakpoint(vm, type, method, descriptor, "entry");
            if (receivers) for (Method ctor : type.methodsByName("<init>"))
                breakpoint(vm, type, "<init>", ctor.signature(), "constructor");
        }
        if (exceptions.isEmpty()) return;
        if (exceptions.contains(type.name())) {
            ExceptionRequest request = vm.eventRequestManager().createExceptionRequest(type, true, true);
            request.putProperty("exactException", type);
            request.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            request.enable();
        }
        if (type.name().equals("UpgradeObservation")) {
            breakpoint(vm, type, "writeFailure", "(Ljava/io/BufferedWriter;Ljava/lang/Throwable;)V", "failure");
            breakpoint(vm, type, "rootMessage", "(Ljava/lang/Throwable;)Ljava/lang/String;", "root");
        }
    }

    private static void watch(VirtualMachine vm, String name) {
        ClassPrepareRequest prepare = vm.eventRequestManager().createClassPrepareRequest();
        prepare.addClassFilter(name);
        prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        prepare.enable();
    }

    // A Java Throwable can have its stack replaced. Snapshot the actual throwing thread and
    // retain only events below observe(). The catcher selects the escaping object by JDI identity.
    private static String digest(byte[] bytes) throws Exception {
        return Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private static List<String> throwingStack(ExceptionEvent event, String observer, String entry,
                                               Set<Long> sites) throws Exception {
        List<String> result = new ArrayList<>();
        Location catcher = event.catchLocation();
        boolean caughtBelow = false, escapesEntry = false;
        for (StackFrame frame : event.thread().frames()) {
            Location location = frame.location();
            ReferenceType type = location.declaringType();
            Method method = location.method();
            String member = type.name() + "#" + method.name() + method.signature();
            if (member.indexOf('\t') >= 0 || member.indexOf('\r') >= 0 || member.indexOf('\n') >= 0)
                return null;
            if (member.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) {
                if (event.virtualMachine().classesByName(observer).size() != 1) return null;
                result.add("observer\t" + location.codeIndex());
                if (escapesEntry && sites.contains(location.codeIndex())) result.add("escape\t" + entry);
                return result;
            }
            // An exception caught inside the selected call has not crossed its boundary.
            // A finally block that rethrows it generates another event for the same object.
            if (catcher != null && method.equals(catcher.method())) caughtBelow = true;
            if (member.equals(entry) && !caughtBelow) escapesEntry = true;
            // A class loaded by two class loaders cannot be attributed by a name in the JVM load log.
            if (event.virtualMachine().classesByName(type.name()).size() == 1) {
                String origin = result.isEmpty() && location.equals(event.location()) ? "location\t" : "";
                if (!origin.isEmpty() && (type.classLoader() == null || (type.classLoader().referenceType().classLoader() == null
                        && type.classLoader().referenceType().name().equals("jdk.internal.loader.ClassLoaders$PlatformClassLoader")))) {
                    result.add("runtimeLocation\t" + member + "\t" + location.codeIndex() + "\t" + location.lineNumber());
                }
                result.add(origin + member + "\t" + location.codeIndex() + "\t" + location.lineNumber());
                if (!origin.isEmpty() && !method.isNative() && event.virtualMachine().canGetBytecodes()
                        && event.virtualMachine().canGetConstantPool()) {
                    String error = event.exception().referenceType().name();
                    if (error.equals("java.lang.NoSuchFieldError") || error.equals("java.lang.NoSuchMethodError")
                            || error.equals("java.lang.IncompatibleClassChangeError")) {
                        result.add("methodBytes\t" + digest(method.bytecodes()) + "\t" + digest(type.constantPool()));
                    }
                }
            }
        }
        return null;
    }

    /** Substitute only a proved integral result, at the entry of that exact loaded static method. */
    private static final class CheckedReplay {
        final String helper, consumer, startup, startupWithin, code, pool;
        final Map<String, Long> table = new LinkedHashMap<>();

        CheckedReplay(String path) throws IOException {
            List<String> lines = Files.readAllLines(Paths.get(path), StandardCharsets.UTF_8);
            helper = lines.get(0); code = lines.get(1); pool = lines.get(2);
            consumer = lines.get(3); startup = lines.get(4); startupWithin = lines.get(5);
            for (String row : lines.subList(6, lines.size())) {
                String[] pair = row.split("\t", -1);
                table.put(pair[0], Long.parseLong(pair[1]));
            }
        }

        static String entry(Location loc) {
            return loc.declaringType().name() + "#" + loc.method().name() + loc.method().signature();
        }

        void bind(VirtualMachine vm, ReferenceType type) {
            for (String target : Arrays.asList(helper, startup)) {
                int hash = target.indexOf('#'), paren = target.indexOf('(', hash);
                if (type.name().equals(target.substring(0, hash))) {
                    breakpoint(vm, type, target.substring(hash + 1, paren), target.substring(paren),
                               target.equals(helper) ? "checked" : "startup");
                }
            }
        }

        void apply(BreakpointEvent hit, boolean premise, String observer) throws Exception {
            List<StackFrame> frames = hit.thread().frames();
            boolean observed = false, startupScope = false;
            for (StackFrame f : frames) {
                String name = entry(f.location());
                if (name.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) observed = true;
                if (name.equals(startupWithin)) startupScope = true;
            }
            if (!observed) return;
            List<Value> values = frames.get(0).getArgumentValues();
            if (premise) {
                if (!startupScope) return;
                String value = "entered";
                List<Value> resourceValues = new ArrayList<>(values);
                ObjectReference receiver = frames.get(0).thisObject();
                if (receiver != null && receiver.referenceType().name().equals("java.net.URL")) resourceValues.add(receiver);
                for (Value arg : resourceValues) {
                    if (arg instanceof com.sun.jdi.StringReference)
                        value = ((com.sun.jdi.StringReference)arg).value();
                    if (arg instanceof ObjectReference && arg.type().name().equals("java.net.URL")) {
                        ObjectReference url = (ObjectReference)arg;
                        Value file = url.getValue(url.referenceType().fieldByName("file"));
                        if (file instanceof com.sun.jdi.StringReference) value = ((com.sun.jdi.StringReference)file).value();
                    }
                }
                System.err.println("UPGRADE-STARTUP " + encoded(value));
                return;
            }
            if (frames.size() < 2 || !entry(frames.get(1).location()).equals(consumer)) return;
            Location loc = hit.location();
            if (!loc.method().isStatic() || loc.method().isSynchronized() || loc.codeIndex() != 0
                    || !digest(loc.method().bytecodes()).equals(code) || !digest(loc.declaringType().constantPool()).equals(pool)
                    || hit.virtualMachine().classesByName(loc.declaringType().name()).size() != 1)
                throw new IllegalStateException("loaded helper differs from the proved static body");
            List<String> args = new ArrayList<>();
            for (Value v : values) args.add(Long.toString(((com.sun.jdi.PrimitiveValue)v).longValue()));
            String key = String.join(",", args);
            if (!table.containsKey(key)) return;
            long result = table.get(key);
            VirtualMachine vm = hit.virtualMachine();
            Value returned;
            switch (helper.charAt(helper.length() - 1)) {
                case 'Z': returned = vm.mirrorOf(result != 0); break;
                case 'C': returned = vm.mirrorOf((char)result); break;
                case 'I': returned = vm.mirrorOf((int)result); break;
                case 'J': returned = vm.mirrorOf(result); break;
                default: throw new IllegalStateException("unsupported result type");
            }
            long bci = frames.get(1).location().codeIndex();
            hit.thread().forceEarlyReturn(returned);
            System.err.println("UPGRADE-SUBSTITUTED " + encoded("{\"caller\":\"" + consumer
                + "\",\"bci\":" + bci + ",\"args\":[" + key + "],\"result\":" + result + "}"));
        }
    }

    private static String invocation(LocatableEvent hit, String observer, Set<Long> sites) throws Exception {
        String dispatched = null;
        for (StackFrame frame : hit.thread().frames()) {
            Method method = frame.location().method();
            String name = method.declaringType().name() + "#" + method.name() + method.signature();
            if (name.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) {
                long pc = frame.location().codeIndex();
                return dispatched != null && sites.contains(pc) ? pc + "\t" + dispatched : null;
            }
            dispatched = name;
        }
        return null;
    }

    // Inspect standard numeric return objects without executing injected code in the original JVM.
    private static String numericReturn(Value value) {
        if (value == null) return "null";
        ObjectReference object = (ObjectReference)value;
        ReferenceType type = object.referenceType();
        String number;
        if (type.name().equals("java.math.BigInteger")) {
            com.sun.jdi.ArrayReference mag = (com.sun.jdi.ArrayReference)object.getValue(type.fieldByName("mag"));
            java.nio.ByteBuffer bytes = java.nio.ByteBuffer.allocate(mag.length() * 4);
            for (Value limb : mag.getValues()) bytes.putInt(((com.sun.jdi.IntegerValue)limb).value());
            int sign = ((com.sun.jdi.IntegerValue)object.getValue(type.fieldByName("signum"))).value();
            number = new java.math.BigInteger(sign, bytes.array()).toString();
        } else {
            Field field = type.fieldByName("value");
            if (field == null || !(object.getValue(field) instanceof com.sun.jdi.PrimitiveValue))
                return "unsupported " + type.name();
            number = object.getValue(field).toString();
        }
        return type.name() + "\t" + number;
    }

    public static void main(String[] args) throws Exception {
        String substitution = System.getProperty("upgrade.checked.table");
        CheckedReplay checked = substitution == null ? null : new CheckedReplay(substitution);
        String entry = args[0];
        int hash = entry.indexOf('#'), paren = entry.indexOf('(', hash);
        String owner = entry.substring(0, hash);
        String method = entry.substring(hash + 1, paren);
        String descriptor = entry.substring(paren);
        String observer = args[5];
        Set<String> exceptions = new LinkedHashSet<>();
        if (!args[6].isEmpty()) exceptions.addAll(Arrays.asList(args[6].split(",")));
        Set<Long> sites = new HashSet<>();
        for (String index : args[4].split(",")) sites.add(Long.parseLong(index));
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        Map<String, Connector.Argument> launch = connector.defaultArguments();
        launch.get("home").setValue(args[1]);
        launch.get("options").setValue("-Xmx384m -Duser.timezone=UTC -Duser.language=en -Duser.country=US "
                + quote("-Djava.io.tmpdir=" + args[2]) + " " + quote("-Duser.home=" + args[2])
                + " " + quote("-Dupgrade.observation.file=" + Paths.get(args[2], "observation.txt"))
                + " -verbose:class -cp " + quote(args[3]));
        StringBuilder main = new StringBuilder("UpgradeObservation ").append(quote(observer));
        for (String argument : Arrays.copyOfRange(args, 7, args.length)) main.append(' ').append(quote(argument));
        launch.get("main").setValue(main.toString());
        launch.get("suspend").setValue("true");
        VirtualMachine vm = connector.launch(launch);
        Process child = vm.process();
        OutputStream diagnostics = Files.newOutputStream(Paths.get(args[2], "child.stderr"));
        Thread stdout = forward(child.getInputStream(), System.out), stderr = forward(child.getErrorStream(), diagnostics);
        String entryInvocation = null;
        boolean history = Boolean.getBoolean("upgrade.observe.history");
        boolean numeric = Boolean.getBoolean("upgrade.observe.numeric");
        Map<Long,Integer> historyReceivers = new LinkedHashMap<>();
        Map<Long, List<String>> constructors = new LinkedHashMap<>();
        boolean finished = false;
        Map<String, List<String>> thrown = new LinkedHashMap<>();
        try {
            if (numeric) {
                MethodExitRequest exits = vm.eventRequestManager().createMethodExitRequest();
                exits.addClassFilter(owner);
                exits.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
                exits.enable();
                ExceptionRequest errors = vm.eventRequestManager().createExceptionRequest(null, true, false);
                errors.putProperty("projection", true);
                errors.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
                errors.enable();
            }
            Set<String> watched = new LinkedHashSet<>(exceptions);
            watched.add(owner);
            for (String target : changed) if (target.contains("#")) watched.add(target.substring(0, target.indexOf('#')));
            if (checked != null) {
                watched.add(checked.helper.split("#")[0]);
                watched.add(checked.startup.split("#")[0]);
            }
            if (!exceptions.isEmpty()) watched.add("UpgradeObservation");
            for (String name : watched) {
                watch(vm, name);
                for (ReferenceType type : vm.classesByName(name))
                    if (type.isPrepared()) {
                        install(vm, type, owner, method, descriptor, exceptions);
                        changedBreakpoints(vm, type);
                        if (checked != null) checked.bind(vm, type);
                    }
            }
            while (!finished) {
                EventSet events = vm.eventQueue().remove();
                for (Event event : events) {
                    if (event instanceof ClassPrepareEvent) {
                        ReferenceType type = ((ClassPrepareEvent) event).referenceType();
                        install(vm, type, owner, method, descriptor, exceptions);
                        changedBreakpoints(vm, type);
                        if (checked != null) checked.bind(vm, type);
                    } else if (event instanceof MethodExitEvent) {
                        MethodExitEvent exit = (MethodExitEvent)event;
                        if (CheckedReplay.entry(exit.location()).equals(entry) && invocation(exit, observer, sites) != null)
                            System.err.println("UPGRADE-NUMBER " + numericReturn(exit.returnValue()));
                    } else if (event instanceof ExceptionEvent) {
                        ExceptionEvent raised = (ExceptionEvent) event;
                        if (Boolean.TRUE.equals(raised.request().getProperty("projection"))) {
                            Location catcher = raised.catchLocation();
                            if (catcher != null && catcher.declaringType().name().equals(observer)
                                    && catcher.method().name().equals("observe") && invocation(raised, observer, sites) != null) {
                                for (StackFrame frame : raised.thread().frames()) {
                                    if (CheckedReplay.entry(frame.location()).equals(entry)) {
                                        System.err.println("UPGRADE-NUMBER throws\t" + raised.exception().referenceType().name());
                                        break;
                                    }
                                }
                            }
                            continue;
                        }
                        if (!raised.exception().referenceType().equals(raised.request().getProperty("exactException"))) continue;
                        String id = raised.thread().uniqueID() + "/" + raised.exception().uniqueID();
                        List<String> stack = throwingStack(raised, observer, entry, sites);
                        if (stack != null) {
                            // try-with-resources and finally can rethrow the very same object
                            // from the caller after the library's frame has been unwound.
                            List<String> eventsForObject = thrown.remove(id);
                            if (eventsForObject == null) eventsForObject = new ArrayList<>();
                            if (thrown.size() == 64) thrown.remove(thrown.keySet().iterator().next());
                            if (eventsForObject.size() < 512) {
                                eventsForObject.add("event");
                                eventsForObject.addAll(stack);
                            } else if (!eventsForObject.get(eventsForObject.size() - 1).equals("truncated")) {
                                eventsForObject.add("truncated");
                            }
                            thrown.put(id, eventsForObject);
                        }
                    } else if (event instanceof BreakpointEvent) {
                        BreakpointEvent point = (BreakpointEvent) event;
                        String purpose = (String) point.request().getProperty("purpose");
                        if (purpose.equals("checked") || purpose.equals("startup")) {
                            checked.apply(point, purpose.equals("startup"), observer);
                        } else if (purpose.equals("changed")) {
                            if (invocation(point, observer, sites) == null) continue;
                            List<String> chain = new ArrayList<>();
                            for (StackFrame frame : point.thread().frames()) {
                                String declaration = CheckedReplay.entry(frame.location());
                                chain.add(declaration);
                                if (declaration.equals(entry)) break;
                            }
                            if (chain.get(chain.size() - 1).equals(entry)
                                    && vm.classesByName(point.location().declaringType().name()).size() == 1) {
                                System.err.println("UPGRADE-CHANGED " + encoded(String.join("\n", chain)));
                                point.request().disable();
                            }
                        } else if (purpose.equals("constructor")) {
                            if (entryInvocation != null) continue;
                            StackFrame frame = point.thread().frame(0);
                            ObjectReference object = frame.thisObject();
                            if (object == null) continue;
                            long id = object.uniqueID();
                            if (!constructors.containsKey(id) && constructors.size() == 256)
                                constructors.remove(constructors.keySet().iterator().next());
                            List<String> calls = constructors.computeIfAbsent(id, unused -> new ArrayList<>());
                            if (calls.size() < 32 && point.thread().frameCount() > 1) {
                                Location at = point.thread().frame(1).location();
                                calls.add(frame.location().method().signature() + "\t" + at.declaringType().name() + "#"
                                        + at.method().name() + at.method().signature() + "\t" + at.codeIndex() + "\n"
                                        + frameShape(frame, false));
                            }
                        } else if (purpose.equals("failure") || purpose.equals("root")) {
                            boolean root = purpose.equals("root");
                            ObjectReference cause = (ObjectReference) point.thread().frame(0).getArgumentValues().get(root ? 0 : 1);
                            List<String> stack = thrown.get(point.thread().uniqueID() + "/" + cause.uniqueID());
                            if (stack != null) {
                                String marker = root ? "UPGRADE-ROOT-STACK " + cause.referenceType().name() + " " : "UPGRADE-THROW-STACK ";
                                System.err.println(marker + Base64.getEncoder().encodeToString(
                                        String.join("\n", stack).getBytes(StandardCharsets.UTF_8)));
                            }
                        } else if (vm.classesByName(owner).size() == 1 && vm.classesByName(observer).size() == 1) {
                            String site = invocation(point, observer, sites);
                            if (site != null) {
                                entryInvocation = site;
                                ObjectReference instance = point.thread().frame(0).thisObject();
                                if (history) {
                                    int alias = instance == null ? -1 : historyReceivers.computeIfAbsent(
                                            instance.uniqueID(), unused -> historyReceivers.size());
                                    System.err.println("UPGRADE-PUBLIC-CALL " + alias);
                                }
                                System.err.println("UPGRADE-IMPLEMENTATION " + CheckedReplay.entry(point.location()) + "\t"
                                        + (instance == null ? "static" : instance.referenceType().name()));
                                if (receivers) {
                                    StackFrame frame = point.thread().frame(0);
                                    ObjectReference object = frame.thisObject();
                                    System.err.println("UPGRADE-RECEIVER " + encoded(frameShape(frame, true)));
                                    if (object != null && constructors.containsKey(object.uniqueID()))
                                        for (String call : constructors.get(object.uniqueID()))
                                            System.err.println("UPGRADE-CONSTRUCTOR " + encoded(call));
                                }
                                if (!history) point.request().disable();
                            }
                        }
                    } else if (event instanceof VMDisconnectEvent) {
                        finished = true;
                    }
                }
                if (!finished) events.resume();
            }
        } catch (VMDisconnectedException e) {
            // A normal child shutdown can disconnect after VMDeath before the next queue read.
            finished = true;
        } finally {
            if (!finished && child.isAlive()) child.destroy();
            stdout.join();
            stderr.join();
            diagnostics.close();
        }
        int status = child.waitFor();
        if (entryInvocation != null) {
            System.err.println("UPGRADE-HIT " + entry);
            System.err.println("UPGRADE-CALL-SITE " + entryInvocation);
        }
        System.exit(status);
    }
}
