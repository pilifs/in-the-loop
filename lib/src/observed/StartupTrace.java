import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.nio.charset.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Observe a single normal return from a selected boundary in an unmodified VM.
 * No method is invoked in the debuggee. Breakpoints live only inside that boundary. */
public final class StartupTrace {
    private static final String CHARSET = "java.nio.charset.Charset";
    private static final String DEFAULT = "defaultCharset()Ljava/nio/charset/Charset;";
    private static final String BYTES = "getBytes()[B";
    private final VirtualMachine vm;
    private final EventRequestManager requests;
    private final String owner, selector;
    private final List<EventRequest> active = new ArrayList<>();
    private final List<String> events = new ArrayList<>();
    private final Deque<Call> calls = new ArrayDeque<>();
    private ThreadReference thread;
    private boolean finished;

    private static final class Call {
        final String operation, frames;
        final int depth;
        final MethodExitRequest exit;
        String input, charset;
        Call(String operation, String frames, int depth, MethodExitRequest exit) {
            this.operation = operation; this.frames = frames; this.depth = depth; this.exit = exit;
        }
    }

    private StartupTrace(VirtualMachine vm, String boundary) {
        this.vm = vm;
        requests = vm.eventRequestManager();
        int hash = boundary.indexOf('#');
        owner = boundary.substring(0, hash);
        selector = boundary.substring(hash + 1);
    }

    private static String quote(String text) { return ObservedInitializer.text(text); }
    private static String method(Method method) { return method.name() + method.signature(); }

    private BreakpointRequest breakpoint(ReferenceType type, String selected) {
        Method method = type.methods().stream().filter(m -> method(m).equals(selected)).findFirst().orElseThrow();
        BreakpointRequest request = requests.createBreakpointRequest(method.location());
        request.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        request.enable();
        return request;
    }

    private MethodExitRequest exitFor(ReferenceType type, ThreadReference thread) {
        MethodExitRequest exit = requests.createMethodExitRequest();
        exit.addClassFilter(type);
        exit.addThreadFilter(thread);
        exit.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
        exit.enable();
        return exit;
    }

    private ReferenceType bootstrap(String name) {
        List<ReferenceType> types = vm.classesByName(name).stream().filter(t -> t.classLoader() == null && t.isPrepared()).toList();
        if (types.size() != 1) throw new IllegalStateException("unbound bootstrap class " + name);
        return types.get(0);
    }

    private void begin(BreakpointEvent at) {
        if (thread != null || finished) throw new IllegalStateException("repeated or overlapping startup boundary");
        thread = at.thread();
        active.add(exitFor(at.location().declaringType(), thread));
        active.add(breakpoint(bootstrap(CHARSET), DEFAULT));
        active.add(breakpoint(bootstrap("java.lang.String"), BYTES));
        ThreadStartRequest start = requests.createThreadStartRequest();
        start.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        start.enable();
        active.add(start);
    }

    private static String frames(ThreadReference thread) throws Exception {
        List<String> frames = new ArrayList<>();
        for (StackFrame frame : thread.frames()) {
            Location l = frame.location();
            frames.add(quote(l.declaringType().name() + "#" + method(l.method()) + "@" + l.codeIndex()));
        }
        return "[" + String.join(",", frames) + "]";
    }

    private void enter(BreakpointEvent at) throws Exception {
        if (thread == null || !at.thread().equals(thread)) throw new IllegalStateException("concurrent charset use during startup");
        if (calls.size() + events.size() >= 512) throw new IllegalStateException("startup charset event limit");
        String op = method(at.location().method());
        Call call = new Call(op, frames(thread), thread.frameCount(), exitFor(at.location().declaringType(), thread));
        if (op.equals(BYTES)) {
            call.input = ((StringReference) thread.frame(0).thisObject()).value();
            if (call.input.length() > 65536) throw new IllegalStateException("default encoding exceeds observation bound");
        }
        calls.push(call);
    }

    private static String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private void returned(MethodExitEvent at) throws Exception {
        if (at.method().declaringType().name().equals(owner) && method(at.method()).equals(selector)) {
            if (!calls.isEmpty()) throw new IllegalStateException("charset operation did not return normally");
            requests.deleteEventRequests(active);
            thread = null;
            finished = true;
            return;
        }
        Call call = calls.peek();
        if (call == null || at.request() != call.exit || !method(at.method()).equals(call.operation)
                || at.thread().frameCount() != call.depth) return;
        calls.pop();
        requests.deleteEventRequest(call.exit);
        String result;
        if (call.operation.equals(DEFAULT)) {
            ObjectReference value = (ObjectReference) at.returnValue();
            ReferenceType type = value.referenceType();
            Field name = bootstrap(CHARSET).fieldByName("name");
            String charset = ((StringReference) value.getValue(name)).value();
            if (type.classLoader() != null || !"java.base".equals(type.module().name())
                    || !(charset.equals("UTF-8") && type.name().equals("sun.nio.cs.UTF_8")
                    || charset.equals("US-ASCII") && type.name().equals("sun.nio.cs.US_ASCII")))
                throw new IllegalStateException("unsupported default charset implementation " + type.name());
            if (!calls.isEmpty() && calls.peek().operation.equals(BYTES)) calls.peek().charset = charset;
            result = "\"canonical\":" + quote(charset) + ",\"implementation\":" + quote(type.name());
        } else {
            if (call.charset == null) throw new IllegalStateException("getBytes did not read the default charset");
            byte[] expected = call.input.getBytes(Charset.forName(call.charset));
            ArrayReference actual = (ArrayReference) at.returnValue();
            if (actual.length() != expected.length) throw new IllegalStateException("default encoder length mismatch");
            List<Value> bytes = actual.getValues();
            for (int i = 0; i < expected.length; i++) {
                if (((ByteValue) bytes.get(i)).value() != expected[i]) throw new IllegalStateException("default encoder byte mismatch");
            }
            // Hash Java code units, including unpaired surrogates, without exposing application text.
            var units = java.nio.ByteBuffer.allocate(2 * call.input.length());
            for (int i = 0; i < call.input.length(); i++) units.putChar(call.input.charAt(i));
            result = "\"canonical\":" + quote(call.charset) + ",\"utf16Sha256\":" + quote(digest(units.array()))
                    + ",\"bytesSha256\":" + quote(digest(expected)) + ",\"length\":" + expected.length;
        }
        events.add("{\"operation\":" + quote(call.operation) + ",\"stack\":" + call.frames + "," + result + "}");
    }

    private void record() throws Exception {
        if (!vm.canGetMethodReturnValues()) throw new IllegalStateException("JDI method return values unavailable");
        ClassPrepareRequest prepare = requests.createClassPrepareRequest();
        prepare.addClassFilter(owner);
        prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        prepare.enable();
        for (ReferenceType type : vm.classesByName(owner)) if (type.isPrepared()) breakpoint(type, selector);
        boolean disconnected = false;
        while (!disconnected) {
            EventSet set = vm.eventQueue().remove(60000);
            if (set == null) throw new IllegalStateException("startup trace timed out");
            for (Event event : set) {
                if (event instanceof ClassPrepareEvent e) breakpoint(e.referenceType(), selector);
                else if (event instanceof BreakpointEvent e) {
                    if (e.location().declaringType().name().equals(owner) && method(e.location().method()).equals(selector)) begin(e);
                    else enter(e);
                } else if (event instanceof MethodExitEvent e) returned(e);
                else if (event instanceof ThreadStartEvent && thread != null) throw new IllegalStateException("thread started inside observed startup boundary");
                else if (event instanceof VMDisconnectEvent) disconnected = true;
            }
            if (!disconnected) set.resume();
        }
        if (!finished) throw new IllegalStateException("startup boundary did not return normally");
    }

    private static String launchArgs(List<String> args) {
        var result = new ArrayList<String>();
        for (String arg : args) {
            if (arg.indexOf('"') >= 0) throw new IllegalArgumentException("embedded JDI launch quote");
            result.add("\"" + arg + "\"");
        }
        return String.join(" ", result);
    }

    private static Thread copy(InputStream in, PrintStream out) {
        Thread worker = new Thread(() -> { try (in) { in.transferTo(out); } catch (IOException e) { throw new UncheckedIOException(e); } });
        worker.start();
        return worker;
    }

    public static void main(String[] args) throws Exception {
        List<String> all = Arrays.asList(args);
        int split = all.indexOf("--main");
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        Map<String, Connector.Argument> launch = connector.defaultArguments();
        launch.get("home").setValue(System.getProperty("java.home"));
        launch.get("options").setValue(launchArgs(all.subList(2, split)));
        launch.get("main").setValue(launchArgs(all.subList(split + 1, all.size())));
        VirtualMachine vm = connector.launch(launch);
        Process child = vm.process();
        try {
            Thread out = copy(child.getInputStream(), System.out), err = copy(child.getErrorStream(), System.err);
            StartupTrace trace = new StartupTrace(vm, args[1]);
            trace.record();
            if (child.waitFor() != 0) throw new IllegalStateException("subject JVM failed");
            out.join(); err.join();
            Files.writeString(Path.of(args[0]), "{\"schema\":\"jvm-startup-trace/v1\",\"boundary\":" + quote(args[1])
                    + ",\"events\":[" + String.join(",", trace.events) + "]}\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
        } finally {
            if (child.isAlive()) child.destroyForcibly().waitFor();
        }
    }
}
