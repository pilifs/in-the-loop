package foundation;

import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Observe the exact wrap operands and downstream use on the original, unmodified classes. */
public final class BufferSites {
    public static int selector;

    static void calls(String number) throws Exception {
        boolean oldExample = number.equals("355");
        Class<?> adapter = Class.forName(oldExample ? "organic.WritableBuffer" : "organic.DecimalWindow");
        var call = adapter.getMethod(oldExample ? "directLimit" : "cursor", int.class);
        for (selector = 0; selector < (oldExample ? 21 : 12); selector++)
            System.out.println("ROW\t" + selector + "\t" + call.invoke(null, selector));
    }

    static final String BUFFER = "java.nio.ByteBuffer";
    static final String DECIMAL = "org.apache.avro.Conversions$DecimalConversion";
    static final String WRAP = "([BII)Ljava/nio/ByteBuffer;";
    static final String DEC = "(Ljava/nio/ByteBuffer;Lorg/apache/avro/Schema;Lorg/apache/avro/LogicalType;)Ljava/math/BigDecimal;";

    static void install(VirtualMachine vm, ReferenceType type, String name) {
        String method = name.equals(BUFFER) ? "wrap" : "fromBytes";
        List<Method> selected = type.methodsByName(method, name.equals(BUFFER) ? WRAP : DEC);
        if (selected.size() != 1 || !selected.get(0).declaringType().equals(type) ||
                (name.equals(BUFFER) && type.classLoader() != null)) throw new IllegalStateException("ambiguous method " + name);
        BreakpointRequest point = vm.eventRequestManager().createBreakpointRequest(selected.get(0).location());
        point.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
        point.enable();
    }

    static int integer(Value value) { return ((IntegerValue)value).value(); }
    static String digest(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    static void event(BreakpointEvent hit, String number, Map<Integer,Long> arrays,
                      Map<Long,Integer> pending, Map<Integer,Long> returnedViews) throws Exception {
        var frames = hit.thread().frames();
        Method target = hit.location().method();
        boolean wrapping = target.declaringType().name().equals(BUFFER);
        int index = 1;
        // The one-argument JDK wrapper delegates to the three-argument overload.
        if (wrapping && frames.get(index).location().declaringType().name().equals(BUFFER) &&
                frames.get(index).location().method().signature().equals("([B)Ljava/nio/ByteBuffer;")) index++;
        Location caller = frames.get(index).location();
        String expected = number.equals("355") ? "org.apache.avro.hadoop.io.AvroDatumConverterFactory$BytesWritableConverter"
                                              : "organic.DecimalWindow";
        if (!caller.declaringType().name().equals(expected)) return;
        String name = number.equals("355") ? "convert" : (wrapping ? "buffer" : "cursor");
        if (!caller.method().name().equals(name)) return;
        VirtualMachine vm = hit.virtualMachine();
        var profiles = vm.classesByName("foundation.BufferSites");
        if (profiles.size() != 1 || vm.classesByName(expected).size() != 1 ||
                vm.classesByName(target.declaringType().name()).size() != 1) throw new IllegalStateException("ambiguous loader");
        int code = integer(profiles.get(0).getValue(profiles.get(0).fieldByName("selector")));
        var args = frames.get(0).getArgumentValues();
        int start, length, capacity;
        if (wrapping) {
            ArrayReference backing = (ArrayReference)args.get(0);
            capacity = backing.length();
            start = integer(args.get(1)); length = integer(args.get(2));
            if (arrays.put(code, backing.uniqueID()) != null) throw new IllegalStateException("repeated wrap in one input");
            if (pending.put(hit.thread().uniqueID(), code) != null) throw new IllegalStateException("nested selected wrap");
        } else {
            ObjectReference view = (ObjectReference)args.get(0);
            if (!Objects.equals(returnedViews.get(code), view.uniqueID())) throw new IllegalStateException("decimal consumes another buffer");
            if (!view.referenceType().name().equals("java.nio.HeapByteBuffer") || view.referenceType().classLoader() != null)
                throw new IllegalStateException("unexpected decimal buffer type");
            ReferenceType t = view.referenceType();
            ArrayReference hb = (ArrayReference)view.getValue(t.fieldByName("hb"));
            if (!Objects.equals(arrays.get(code), hb.uniqueID())) throw new IllegalStateException("decimal consumes another array");
            start = integer(view.getValue(t.fieldByName("position")));
            length = integer(view.getValue(t.fieldByName("limit"))) - start;
            capacity = integer(view.getValue(t.fieldByName("capacity")));
            if (capacity != hb.length() || integer(view.getValue(t.fieldByName("offset"))) != 0)
                throw new IllegalStateException("unexpected decimal view");
        }
        System.out.println(String.join("\t", "SITE", Integer.toString(code), wrapping ? "wrap" : "decimal",
                Integer.toString(capacity), Integer.toString(start), Integer.toString(length),
                expected + "#" + name + caller.method().signature(), Long.toString(caller.codeIndex()),
                digest(caller.method().bytecodes()), digest(caller.declaringType().constantPool()),
                target.declaringType().name() + "#" + target.name() + target.signature(), digest(target.bytecodes())));
    }

    static void trace(String number, String cp, String tmp) throws Exception {
        if (cp.contains("\"") || tmp.contains("\"")) throw new IllegalArgumentException("unrepresentable launcher path");
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        var args = connector.defaultArguments();
        args.get("main").setValue("foundation.BufferSites calls " + number);
        args.get("options").setValue("-XX:ActiveProcessorCount=2 -Djava.io.tmpdir=\"" + tmp + "\" -classpath \"" + cp + "\"");
        VirtualMachine vm = connector.launch(args);
        Process process = vm.process();
        Thread out = Thread.startVirtualThread(() -> pipe(process.getInputStream(), System.out));
        Thread err = Thread.startVirtualThread(() -> pipe(process.getErrorStream(), System.err));
        Map<Integer, Long> arrays = new HashMap<>();
        Map<Long, Integer> pending = new HashMap<>();
        Map<Integer, Long> returnedViews = new HashMap<>();
        try {
            if (!vm.canGetMethodReturnValues()) throw new IllegalStateException("JVM cannot identify the returned view");
            var exits = vm.eventRequestManager().createMethodExitRequest();
            exits.addClassFilter(BUFFER);
            exits.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            exits.enable();
            for (String name : number.equals("355") ? List.of(BUFFER) : List.of(BUFFER, DECIMAL)) {
                var request = vm.eventRequestManager().createClassPrepareRequest();
                request.addClassFilter(name);
                request.setSuspendPolicy(EventRequest.SUSPEND_ALL);
                request.enable();
                for (ReferenceType t : vm.classesByName(name)) if (t.isPrepared()) install(vm, t, name);
            }
            while (true) {
                EventSet events = vm.eventQueue().remove(90000);
                if (events == null) throw new IllegalStateException("no progress from traced JVM");
                for (Event e : events) {
                    if (e instanceof ClassPrepareEvent c) install(vm, c.referenceType(), c.referenceType().name());
                    if (e instanceof BreakpointEvent b) event(b, number, arrays, pending, returnedViews);
                    if (e instanceof MethodExitEvent x && x.method().name().equals("wrap") && x.method().signature().equals(WRAP)) {
                        Integer code = pending.remove(x.thread().uniqueID());
                        if (code != null) returnedViews.put(code, ((ObjectReference)x.returnValue()).uniqueID());
                    }
                    if (e instanceof VMDisconnectEvent) return;
                }
                events.resume();
            }
        } catch (VMDisconnectedException finished) {
            // Process status and equality with the plain JVM answer are checked by both callers.
        } finally {
            if (process.isAlive() && !process.waitFor(2, java.util.concurrent.TimeUnit.SECONDS)) process.destroyForcibly();
            out.join(); err.join();
            if (process.waitFor() != 0) throw new IllegalStateException("traced JVM failed");
            if (!returnedViews.keySet().equals(arrays.keySet()) || !pending.isEmpty())
                throw new IllegalStateException("missing normal return from a selected wrap");
        }
    }

    static void pipe(InputStream input, PrintStream output) {
        try { input.transferTo(output); } catch (IOException e) { throw new UncheckedIOException(e); }
    }

    public static void main(String[] args) throws Exception {
        if (args[0].equals("calls")) calls(args[1]); else trace(args[1], args[2], args[3]);
    }
}
