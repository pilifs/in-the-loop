import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.*;

final class CaseFrames extends FrameValues {
    static final String TASK = "net.lingala.zip4j.tasks.RenameFilesTask";
    static final String DESC = "(Lnet/lingala/zip4j/model/FileHeader;Ljava/util/Map;)Ljava/util/Map$Entry;";
    static boolean prediction;
    static String[] pending;
    static Set<String> watched() { return Set.of(TASK); }
    static void install(VirtualMachine vm, ReferenceType type) {
        if (!type.name().equals(TASK)) return;
        bind(type,"getCorrespondingEntryFromMap",DESC,32,"predicate");
        if (config.getProperty("mode").equals("original"))
            for (String pc : config.getProperty("returns").split(","))
                bind(type,"getCorrespondingEntryFromMap",DESC,Integer.parseInt(pc),"returned");
    }
    static void thrown(ExceptionEvent e) { }
    static String string(Value value) {
        String s = ((StringReference)value).value();
        need(s.matches("[a-z/]+"), "outside the registered ASCII name domain");
        return s;
    }
    static void hit(BreakpointEvent point, String phase) throws Exception {
        ThreadReference thread = point.thread();
        List<StackFrame> frames = thread.frames();
        StackFrame top = frames.getFirst();
        Location at = point.location(), consumer = frames.get(1).location();
        need(consumer.declaringType().name().equals(TASK) && consumer.method().name().equals("executeTask")
                && find(frames,config.getProperty("public")) != null
                && find(frames,"UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;") != null, "wrong rename consumer");
        need(hash(at.method().bytecodes()).equals(config.getProperty("code"))
                && hash(at.declaringType().constantPool()).equals(config.getProperty("pool")), "stale match proof");
        if (phase.equals("returned")) {
            need(pending != null && prediction == (at.codeIndex() != Integer.parseInt(config.getProperty("rejectReturn"))),
                    "original return disagrees with qualified predicate");
            mark(pending); pending = null; return;
        }
        ObjectReference header = (ObjectReference)top.getArgumentValues().get(0);
        ObjectReference map = (ObjectReference)top.getArgumentValues().get(1);
        ObjectReference entry = (ObjectReference)top.getValue(top.visibleVariableByName("fileHeaderToBeRenamed"));
        need(header.referenceType().name().equals("net.lingala.zip4j.model.FileHeader") && map.referenceType().name().equals("java.util.HashMap")
                && ((IntegerValue)get(map,"size")).value() == 1 && entry.referenceType().name().equals("java.util.HashMap$Node"),
                "outside the single original HashMap node scope");
        List<Value> buckets = ((ArrayReference)get(map,"table")).getValues().stream().filter(Objects::nonNull).toList();
        need(buckets.equals(List.of(entry)) && get(entry,"next") == null, "different map entry or successor");
        String key = string(get(entry,"key")), target=string(get(entry,"value")), name=string(get(header,"fileName"));
        boolean fixed = config.getProperty("side").equals("new");
        prediction = fixed ? (key.endsWith("/") && name.startsWith(key)) || name.equals(key) : name.startsWith(key);
        boolean original = config.getProperty("mode").equals("original");
        String[] record = {original ? "original" : "applied",name,key,target,"" + prediction,site(consumer)};
        if (original) { need(pending == null,"overlapping matcher runs"); pending = record; }
        else { mark(record); thread.forceEarlyReturn(prediction ? entry : null); }
    }
}
