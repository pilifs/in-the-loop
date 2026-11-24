import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.*;

final class CaseFrames extends FrameValues {
    static final String BASE = "org.apache.maven.artifact.versioning.";
    static final String CMP = BASE + "ComparableVersion", RANGE = BASE + "VersionRange", ART = BASE + "ArtifactVersion";
    static final String CD = "(Lorg/apache/maven/artifact/versioning/ComparableVersion;)I";
    static final String MATCH = "(Ljava/util/List;)Lorg/apache/maven/artifact/versioning/ArtifactVersion;";
    static Set<String> watched() { return Set.of(CMP,RANGE); }
    static void thrown(ExceptionEvent e) { }
    static void install(VirtualMachine vm, ReferenceType type) {
        if (type.name().equals(CMP)) bind(type,"compareTo",CD,0,"compare");
        if (type.name().equals(RANGE)) bind(type,"matchVersion",MATCH,0,"match");
    }
    static String shape(ObjectReference item, int remaining) {
        need(remaining > 0, "unexpected parse depth");
        switch (item.referenceType().name()) {
            case CMP + "$IntItem": return "I" + ((IntegerValue)get(item,"value")).value();
            case CMP + "$StringItem": return "S" + ((StringReference)get(item,"value")).value();
            case CMP + "$ListItem":
                int size = ((IntegerValue)get(item,"size")).value();
                need(size >= 0 && size <= 3, "outside parsed list bound");
                List<String> children = new ArrayList<>();
                ArrayReference data = (ArrayReference)get(item,"elementData");
                for (int i=0; i<size; i++) children.add(shape((ObjectReference)data.getValue(i),remaining-1));
                return "L[" + String.join(",",children) + "]";
            default: throw new IllegalStateException("unqualified version item type");
        }
    }
    static void hit(BreakpointEvent point, String purpose) throws Exception {
        ThreadReference thread = point.thread();
        List<StackFrame> stack = thread.frames();
        StackFrame top = stack.getFirst();
        if (purpose.equals("match")) {
            if (id(stack.get(1).location()).equals("UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;"))
                mark("public-match",site(point.location()));
            return;
        }
        String phase = null;
        for (StackFrame frame : stack) {
            Location location = frame.location();
            if (location.declaringType().name().equals(RANGE)) {
                if (location.method().name().equals("matchVersion")) phase = "selection";
                if (location.method().name().equals("createFromVersionSpec")) phase = "construction";
            }
        }
        if (phase == null) return; // excludes the observer's independent highest-version fold
        Location call = stack.get(1).location(), at = point.location();
        need(call.declaringType().name().equals(BASE+"DefaultArtifactVersion") && call.method().name().equals("compareTo")
                && find(stack,"UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;") != null,"different comparator consumer");
        need(hash(at.method().bytecodes()).equals(config.getProperty("code"))
                && hash(at.declaringType().constantPool()).equals(config.getProperty("pool")), "stale comparator proof");
        ObjectReference left = top.thisObject(), right = (ObjectReference)top.getArgumentValues().getFirst();
        need(right.referenceType().name().equals(CMP), "different comparison dispatch");
        String l = ((StringReference)get(left,"value")).value(), r = ((StringReference)get(right,"value")).value();
        String ls = shape((ObjectReference)get(left,"items"),5), rs=shape((ObjectReference)get(right,"items"),5);
        need(ls.equals(config.getProperty("shape."+l)) && rs.equals(config.getProperty("shape."+r)), "stale parsed-version shape");
        String raw = config.getProperty("return."+l+"/"+r);
        need(raw != null,"unqualified comparator arguments");
        mark("compare",phase,l,ls,r,rs,raw,site(call));
        if (config.getProperty("mode").equals("apply")) thread.forceEarlyReturn(point.virtualMachine().mirrorOf(Integer.parseInt(raw)));
    }
}
