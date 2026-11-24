import com.sun.jdi.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Attribute a checked conversion to the exact calendar and cursor supplied at public parse entry. */
final class WeekFrames {
    private static final String PARSER = "org.apache.commons.lang3.time.FastDateParser";
    private static final String FORMAT = "org.apache.commons.lang3.time.FastDateFormat";
    private static final String PARSE = "#parse(Ljava/lang/String;Ljava/text/ParsePosition;Ljava/util/Calendar;)Z";

    private static String entry(StackFrame f) {
        Location loc = f.location();
        return loc.declaringType().name() + "#" + loc.method().name() + loc.method().signature();
    }

    private static Value field(ObjectReference object, String name) {
        return object.getValue(object.referenceType().fieldByName(name));
    }

    private static String hash(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }

    static void initialized(StackFrame publicParse) throws Exception {
        VirtualMachine vm = publicParse.virtualMachine();
        List<ReferenceType> providers = vm.classesByName("org.apache.commons.lang3.time.TimeZones");
        if (providers.size() != 1 || !providers.getFirst().isInitialized()) throw new IllegalStateException("missing live TimeZones initialization");
        ReferenceType zones = providers.getFirst();
        ObjectReference gmt = (ObjectReference) zones.getValue(zones.fieldByName("GMT"));
        ObjectReference delegate = (ObjectReference) field(gmt, "timeZone");
        ObjectReference parser = (ObjectReference) field(publicParse.thisObject(), "parser");
        ObjectReference selected = (ObjectReference) field(parser, "timeZone");
        Field id = vm.classesByName("java.util.TimeZone").getFirst().fieldByName("ID");
        ArrayReference available = (ArrayReference) zones.getValue(zones.fieldByName("SORTED_AVAILABLE_IDS"));
        List<String> ids = new ArrayList<>();
        for (Value value : available.getValues()) ids.add(((StringReference) value).value());
        List<String> reference = new ArrayList<>(Arrays.asList(TimeZone.getAvailableIDs()));
        Collections.sort(reference);
        if (!ids.equals(reference) || !ids.contains("UTC") || !ids.contains("GMT")) throw new IllegalStateException("different JDK zone table");
        String payload = String.join("\t", gmt.referenceType().name(), ((StringReference) delegate.getValue(id)).value(),
                ((StringReference) selected.getValue(id)).value(), zones.getValue(zones.fieldByName("JAVA_25")).toString(),
                Integer.toString(ids.size()), hash(String.join("\n", ids).getBytes(StandardCharsets.UTF_8)),
                hash(zones.methodsByName("<clinit>", "()V").getFirst().bytecodes()), hash(zones.constantPool()));
        System.err.println("WEEK-ZONES " + Base64.getEncoder().encodeToString(payload.getBytes(StandardCharsets.UTF_8)));
    }

    static void record(List<StackFrame> stack, String arguments) throws Exception {
        StackFrame caller = stack.get(2), internal = null, api = null;
        String role;
        ObjectReference recorder;
        if (entry(caller).equals(PARSER + "$WeekDateRecorder#applyWeekDate()V")) {
            role = "normalize";
            recorder = caller.thisObject();
        } else {
            if (!caller.location().method().name().equals("modify") || !entry(stack.get(3)).equals(PARSER +
                    "$NumberStrategy#parse(Lorg/apache/commons/lang3/time/FastDateParser;Ljava/util/Calendar;Ljava/lang/String;Ljava/text/ParsePosition;I)Z")) {
                throw new IllegalStateException("conversion outside the original number strategy");
            }
            role = "parse-digit";
            Field numberField = stack.get(3).location().declaringType().fieldByName("field");
            if (!caller.thisObject().equals(stack.get(3).thisObject()) || !caller.thisObject().getValue(numberField).toString().equals("7")) {
                throw new IllegalStateException("converted number is not the target's day-of-week field");
            }
            recorder = (ObjectReference) stack.get(3).getArgumentValues().get(1);
        }
        for (int i = 3; i + 1 < stack.size(); i++) {
            if (entry(stack.get(i)).equals(PARSER + PARSE) && entry(stack.get(i + 1)).equals(FORMAT + PARSE)) {
                internal = stack.get(i);
                api = stack.get(i + 1);
                break;
            }
        }
        if (api == null || !recorder.referenceType().name().equals(PARSER + "$WeekDateRecorder")
                || !internal.thisObject().equals(field(api.thisObject(), "parser"))
                || !internal.getArgumentValues().equals(api.getArgumentValues())
                || !api.getArgumentValues().get(2).type().name().equals("java.util.GregorianCalendar")
                || !field(recorder, "target").equals(api.getArgumentValues().get(2))) {
            throw new IllegalStateException("lost the caller-owned calendar, cursor or formatter");
        }
        ObjectReference cursor = (ObjectReference) api.getArgumentValues().get(1);
        if (role.equals("parse-digit") && !cursor.equals(stack.get(3).getArgumentValues().get(3))) {
            throw new IllegalStateException("different number strategy cursor");
        }
        Location at = caller.location();
        String payload = String.join("\t", role, arguments, field(cursor, "index").toString(), entry(caller),
                Long.toString(at.codeIndex()), hash(at.method().bytecodes()), hash(at.declaringType().constantPool()));
        System.err.println("WEEK-CONVERSION " + Base64.getEncoder().encodeToString(payload.getBytes(StandardCharsets.UTF_8)));
    }
}
