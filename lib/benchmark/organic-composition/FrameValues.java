import com.sun.jdi.*;
import com.sun.jdi.request.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

class FrameValues {
    static final Properties config = new Properties();
    static {
        try (var reader = Files.newBufferedReader(Path.of(System.getProperty("case.config")))) { config.load(reader); }
        catch (Exception e) { throw new ExceptionInInitializerError(e); }
    }

    static void need(boolean ok, String why) { if (!ok) throw new IllegalStateException(why); }
    static Field field(ReferenceType type, String name) {
        Field f = type.fieldByName(name);
        need(f != null, "missing field " + type.name() + "." + name);
        return f;
    }
    static Value get(ObjectReference object, String name) { return object.getValue(field(object.referenceType(), name)); }
    static Value get(ReferenceType type, String name) { return type.getValue(field(type, name)); }
    static ReferenceType one(VirtualMachine vm, String name) {
        List<ReferenceType> types = vm.classesByName(name);
        need(types.size() == 1, "ambiguous or absent class " + name);
        return types.getFirst();
    }
    static String id(Location at) { return at.declaringType().name() + "#" + at.method().name() + at.method().signature(); }
    static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    static String site(Location at) throws Exception {
        return String.join("\t", id(at), Long.toString(at.codeIndex()), hash(at.method().bytecodes()), hash(at.declaringType().constantPool()));
    }
    static void mark(String... fields) { System.err.println("CASE\t" + String.join("\t", fields)); }
    static void bind(ReferenceType type, String name, String desc, long offset, String role) {
        List<Method> methods = type.methodsByName(name, desc);
        need(methods.size() == 1, "missing original method " + type.name() + "#" + name + desc);
        Location at = methods.getFirst().locationOfCodeIndex(offset);
        need(at != null && at.codeIndex() == offset, "missing original bytecode location");
        BreakpointRequest request = type.virtualMachine().eventRequestManager().createBreakpointRequest(at);
        request.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
        request.putProperty("purpose", "case/" + role);
        request.enable();
    }
    static StackFrame find(List<StackFrame> stack, String member) {
        for (StackFrame f : stack) if (id(f.location()).equals(member)) return f;
        return null;
    }
}
