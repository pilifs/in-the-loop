import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Check key promotion, decimal conversion and the value read on the same original reader. */
final class CaseFrames extends FrameValues {
    static final String BASE = "com.google.gson.";
    static final String READER = BASE + "stream.JsonReader", TREE = BASE + "internal.bind.JsonTreeReader";
    static final String ACCESS = BASE + "internal.JsonReaderInternalAccess", IMPL = READER + "$1";
    static final String ARG = "(Lcom/google/gson/stream/JsonReader;)";
    static final String MAP = BASE + "internal.bind.MapTypeAdapterFactory$Adapter#read" + ARG + "Ljava/util/Map;";
    static final String OBSERVE = "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;";
    static final String PARSE = "java.lang.Integer#parseInt(Ljava/lang/String;)I";
    static final String INTEGER = "java.lang.Integer", ADAPTER = "UpgradeProbe$ValueAdapter";
    static ObjectReference installed, reader, gson, adapter;
    static String argument;
    static int document, expected;

    static Set<String> watched() { return Set.of(READER, IMPL, INTEGER, ADAPTER); }
    static void install(VirtualMachine vm, ReferenceType t) {
        switch (t.name()) {
            case READER -> bind(t, "<clinit>", "()V", Long.parseLong(config.getProperty("installedAt")), "installed");
            case IMPL -> bind(t, "promoteNameToValue", ARG + "V", 0, "promote");
            case INTEGER -> bind(t, "parseInt", "(Ljava/lang/String;)I", 0, "parse");
            case ADAPTER -> bind(t, "read", ARG + "Ljava/lang/String;", 0, "value");
        }
    }

    static void style(VirtualMachine vm, String name, String nl, String indent, boolean spaces) {
        ReferenceType type = one(vm, BASE + "FormattingStyle");
        ObjectReference obj = (ObjectReference) get(type, name);
        need(type.isInitialized() && ((StringReference) get(obj, "newline")).value().equals(nl)
                && ((StringReference) get(obj, "indent")).value().equals(indent)
                && ((BooleanValue) get(obj, "spaceAfterSeparators")).value() == spaces, "unqualified formatting initializer");
    }
    static void active(List<StackFrame> frames) {
        need(reader != null && find(frames, MAP).getArgumentValues().getFirst().equals(reader), "different map reader");
        StackFrame api = find(frames, BASE + "Gson#fromJson(Lcom/google/gson/stream/JsonReader;Lcom/google/gson/reflect/TypeToken;)Ljava/lang/Object;");
        need(api != null && api.getArgumentValues().getFirst().equals(reader), "different public reader");
        if (gson == null) gson = api.thisObject();
        need(gson.equals(api.thisObject()) && find(frames, config.getProperty("entry")) != null, "different public Gson or overload");
    }
    static void qualify(VirtualMachine vm, StringReference arg) throws Exception {
        byte[] bytes = argument.getBytes(StandardCharsets.US_ASCII);
        ArrayReference value = (ArrayReference) get(arg, "value");
        need(value.length() == bytes.length && ((ByteValue) get(arg, "coder")).value() == 0
                && ((BooleanValue) get(arg.referenceType(), "COMPACT_STRINGS")).value(), "different String representation");
        ReferenceType latin = one(vm, "java.lang.CharacterDataLatin1");
        need(latin.isInitialized() && ((ObjectReference) get(latin, "instance")).referenceType().equals(latin), "uninitialized digit provider");
        ArrayReference digits = (ArrayReference) get(latin, "DIGITS");
        for (int i = 0; i < bytes.length; i++) {
            int c = bytes[i];
            need(((ByteValue) value.getValue(i)).value() == c && c >= 48 && c <= 50
                    && ((ByteValue) digits.getValue(c)).value() == c - 48, "unbound decimal digit read");
        }
        for (String id : config.getProperty("methods").split(",")) {
            int hash = id.indexOf('#'), paren = id.indexOf('(', hash);
            ReferenceType type = one(vm, id.substring(0, hash));
            Method m = type.methodsByName(id.substring(hash + 1, paren), id.substring(paren)).getFirst();
            need(type.classLoader() == null && type.isInitialized() && hash(m.bytecodes()).equals(config.getProperty("code." + id))
                    && hash(type.constantPool()).equals(config.getProperty("pool." + id)), "stale or uninitialized decimal method " + id);
        }
    }

    static void hit(BreakpointEvent event, String role) throws Exception {
        var vm = event.virtualMachine();
        List<StackFrame> frames = event.thread().frames();
        StackFrame top = frames.getFirst();
        if (find(frames, OBSERVE) == null) return;
        if (role.equals("installed")) {
            style(vm, "COMPACT", "", "", false);
            style(vm, "PRETTY", "\n", "  ", true);
            installed = (ObjectReference) get(one(vm, ACCESS), "INSTANCE");
            need(installed.referenceType().name().equals(IMPL), "wrong installed accessor");
            mark("installed", site(top.location()), IMPL);
            return;
        }
        StackFrame map = find(frames, MAP);
        if (map == null) return;
        if (role.equals("promote")) {
            need(installed != null && installed.equals(top.thisObject()) && installed.equals(get(one(vm, ACCESS), "INSTANCE"))
                    && frames.get(1).equals(map), "unqualified original key promotion");
            ObjectReference next = (ObjectReference) top.getArgumentValues().getFirst();
            if (!next.equals(reader)) document++;
            reader = next;
            active(frames);
            argument = null;
            mark("promote", Integer.toString(document), reader.referenceType().name(), site(map.location()));
        } else if (role.equals("parse")) {
            Location caller = frames.get(1).location();
            String callerId = id(caller);
            if (!callerId.equals(READER + "#nextInt()I") && !callerId.equals(BASE + "JsonPrimitive#getAsInt()I")) return;
            active(frames);
            need(callerId.equals(config.getProperty("caller")), "wrong reader-specific parse consumer");
            StringReference arg = (StringReference) top.getArgumentValues().getFirst();
            argument = arg.value();
            need(config.containsKey("value." + argument), "outside admitted String contents");
            if (reader.referenceType().name().equals(READER)) {
                need(reader.equals(frames.get(1).thisObject()) && arg.equals(get(reader, "peekedString")), "different streaming key");
            } else {
                StackFrame nextInt = find(frames, TREE + "#nextInt()I");
                ArrayReference stack = (ArrayReference) get(reader, "stack");
                int size = ((IntegerValue) get(reader, "stackSize")).value();
                ObjectReference primitive = frames.get(1).thisObject();
                need(nextInt != null && nextInt.thisObject().equals(reader) && stack.getValue(size-1).equals(primitive)
                        && arg.equals(get(primitive, "value")), "different tree key");
            }
            qualify(vm, arg);
            expected = Integer.parseInt(config.getProperty("value." + argument));
            boolean apply = config.getProperty("mode").equals("apply");
            mark("parse", argument, Integer.toString(expected), Boolean.toString(apply), site(caller));
            if (apply) event.thread().forceEarlyReturn(vm.mirrorOf(expected));
        } else if (role.equals("value")) {
            active(frames);
            if (adapter == null) adapter = top.thisObject();
            need(adapter.equals(top.thisObject()) && reader.equals(top.getArgumentValues().getFirst()) && argument != null,
                    "value read detached from original key conversion");
            ObjectReference key = (ObjectReference) map.getValue(map.visibleVariableByName("key"));
            need(key.referenceType().name().equals(INTEGER) && ((IntegerValue) get(key, "value")).value() == expected,
                    "map adapter consumed a different integer key");
            mark("value", argument, Integer.toString(expected), site(map.location()));
        }
    }

    static void thrown(ExceptionEvent event) throws Exception {
        if (event.catchLocation() == null || !event.catchLocation().declaringType().name().equals(ADAPTER)) return;
        String where = id(event.location());
        if (!where.equals(READER + "#nextString()Ljava/lang/String;") && !where.equals(TREE + "#nextString()Ljava/lang/String;")) return;
        List<StackFrame> frames = event.thread().frames();
        active(frames);
        need(reader.equals(frames.getFirst().thisObject()) && find(frames, ADAPTER + "#read" + ARG + "Ljava/lang/String;").thisObject().equals(adapter),
                "failure on a different reader or registered adapter");
        String line = ((StringReference) get(event.exception(), "detailMessage")).value().split("\n", 2)[0];
        need(line.contains("but was BEGIN_ARRAY") && line.contains(" path "), "unexpected original failure");
        mark("failure", argument, line.substring(line.lastIndexOf(" path ")+6), site(event.location()), site(event.catchLocation()));
    }
}
