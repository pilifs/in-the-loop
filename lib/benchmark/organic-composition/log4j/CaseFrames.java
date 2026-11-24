import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.*;

/** Observe plugin selection and substitute the checked update on the original scheduling receiver. */
final class CaseFrames extends FrameValues {
    static final String CORE = "org.apache.logging.log4j.core.";
    static final String PROC = CORE + "appender.rolling.PatternProcessor", CONV = CORE + "pattern.DatePatternConverter";
    static final String FACTORY = CORE + "pattern.FileDatePatternConverter";
    static final String CACHE = CORE + "config.plugins.processor.PluginCache#loadCacheFiles(Ljava/util/Enumeration;)V";
    static final String OBSERVE = "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;";
    static final String ENTRY = PROC + "#getNextTime(JIZ)J";
    static ObjectReference instance, converter, savedDefault;
    static boolean resourceSeen;
    static long predictedPrev, predictedCurrent;
    static Map<Field,Value> frame;
    static Set<String> watched() { return Set.of("java.net.URL", PROC, CONV, "java.util.Calendar", "java.util.TimeZone"); }
    static void install(VirtualMachine vm, ReferenceType type) {
        switch (type.name()) {
            case "java.net.URL" -> bind(type, "openStream", "()Ljava/io/InputStream;", 0, "resource");
            case "java.util.TimeZone" -> bind(type, "setDefault", "(Ljava/util/TimeZone;)V", 0, "default");
            case CONV -> bind(type, "<init>", "([Ljava/lang/String;)V", 0, "converter");
            case PROC -> {
                bind(type, "updateTime", "()V", 0, "update");
                bind(type, "updateTime", "()V", Long.parseLong(config.getProperty("return")), "returned");
            }
            case "java.util.Calendar" -> bind(type, "createCalendar", "(Ljava/util/TimeZone;Ljava/util/Locale;)Ljava/util/Calendar;", 0, "calendar");
        }
    }
    static void thrown(ExceptionEvent event) { }
    static long number(ObjectReference p, String n) { return ((LongValue) get(p, n)).value(); }
    static String idOfZone(ObjectReference zone) {
        return ((StringReference) zone.getValue(field(one(zone.virtualMachine(), "java.util.TimeZone"), "ID"))).value();
    }
    static void after(ObjectReference p) {
        Map<Field,Value> result = p.getValues(new ArrayList<>(frame.keySet()));
        for (Map.Entry<Field,Value> old : frame.entrySet()) {
            Value expected = switch (old.getKey().name()) {
                case "prevFileTime" -> p.virtualMachine().mirrorOf(predictedPrev);
                case "currentFileTime" -> p.virtualMachine().mirrorOf(predictedCurrent);
                default -> old.getValue();
            };
            need(Objects.equals(expected, result.get(old.getKey())), "wrong poststate for " + old.getKey().name());
        }
        mark("post", Long.toString(predictedPrev), Long.toString(predictedCurrent), Integer.toString(frame.size()));
    }
    static void hit(BreakpointEvent event, String role) throws Exception {
        List<StackFrame> frames = event.thread().frames();
        if (find(frames, OBSERVE) == null) return;
        StackFrame top = frames.getFirst();
        VirtualMachine vm = event.virtualMachine();
        if (role.equals("default")) {
            StackFrame observer = frames.get(1);
            if (!id(observer.location()).equals(OBSERVE)) return;
            ObjectReference original = (ObjectReference) observer.getValue(observer.visibleVariableByName("original"));
            ObjectReference selected = (ObjectReference) top.getArgumentValues().getFirst();
            String phase = savedDefault == null ? "enter" : "restore";
            if (savedDefault == null) savedDefault = original;
            else need(savedDefault.equals(original) && selected.equals(original), "default was not restored to the original object");
            String processZone = System.getProperty("case.zone");
            need(idOfZone(original).equals(processZone) && idOfZone(selected).equals(processZone), "different fresh process default");
            mark("default", phase, idOfZone(original), idOfZone(selected), site(observer.location()));
        } else if (role.equals("resource")) {
            if (!id(frames.get(1).location()).equals(CACHE)) return;
            String url = ((StringReference) get(top.thisObject(), "file")).value();
            need(url.equals(config.getProperty("pluginUrl")), "different plugin metadata URL");
            mark("resource", url, site(frames.get(1).location()));
            resourceSeen = true;
        } else if (role.equals("converter")) {
            StackFrame factory = find(frames, FACTORY + "#newInstance([Ljava/lang/String;)Lorg/apache/logging/log4j/core/pattern/PatternConverter;");
            StackFrame constructor = find(frames, PROC + "#<init>(Ljava/lang/String;)V");
            need(resourceSeen && factory != null && constructor != null, "unqualified converter factory");
            instance = constructor.thisObject();
            converter = top.thisObject();
            ArrayReference args = (ArrayReference) top.getArgumentValues().getFirst();
            List<String> opts = args.getValues().stream().map(v -> ((StringReference) v).value()).toList();
            need(opts.equals(List.of(config.getProperty("options").split(","))), "different date pattern or explicit zone");
            mark("converter", String.join(",", opts), site(factory.location()));
        } else if (role.equals("calendar")) {
            StackFrame schedule = find(frames, ENTRY);
            if (schedule == null) return;
            String zone = idOfZone((ObjectReference) top.getArgumentValues().getFirst());
            need(schedule.thisObject().equals(instance) && zone.equals(config.getProperty("usedZone")), "different scheduling timezone");
            mark("calendar", zone, site(schedule.location()));
        } else if (role.equals("returned")) {
            need(instance.equals(top.thisObject()), "different original update receiver");
            after(instance);
        } else {
            need(top.thisObject().equals(instance) && resourceSeen && converter != null, "unbound schedule receiver");
            List<Value> selected = ((ArrayReference) get(instance, "patternConverters")).getValues();
            need(selected.stream().filter(v -> v instanceof ObjectReference && ((ObjectReference) v).referenceType().name().equals(CONV)).toList().equals(List.of(converter)),
                    "converter did not reach this receiver");
            Field zone = instance.referenceType().fieldByName("timeZone");
            need(zone == null ? config.getProperty("side").equals("old") :
                    config.getProperty("side").equals("new") && idOfZone((ObjectReference) instance.getValue(zone)).equals(config.getProperty("usedZone")),
                    "different constructor-installed zone");
            Location at = top.location();
            need(hash(at.method().bytecodes()).equals(config.getProperty("code")) && hash(at.declaringType().constantPool()).equals(config.getProperty("pool")),
                    "stale updateTime proof");
            long next = number(instance, "nextFileTime"), prev = number(instance, "prevFileTime"), current = number(instance, "currentFileTime");
            boolean timeBased = ((BooleanValue) get(instance, "isTimeBased")).value();
            boolean assign = next != 0 || !timeBased;
            predictedPrev = assign ? next : prev;
            predictedCurrent = assign ? 0 : current;
            frame = instance.getValues(instance.referenceType().allFields().stream().filter(f -> !f.isStatic()).toList());
            boolean apply = config.getProperty("mode").equals("apply");
            mark("update", Long.toString(next), Long.toString(prev), Long.toString(current), Boolean.toString(timeBased), Boolean.toString(apply), site(frames.get(1).location()));
            if (apply) {
                if (assign) {
                    instance.setValue(field(instance.referenceType(), "prevFileTime"), vm.mirrorOf(next));
                    instance.setValue(field(instance.referenceType(), "currentFileTime"), vm.mirrorOf(0L));
                }
                after(instance);
                event.thread().forceEarlyReturn(vm.mirrorOfVoid());
            }
        }
    }
}
