import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.*;

final class CaseFrames extends FrameValues {
    static final String TAG = "org.jsoup.parser.Tag", BUILDER = "org.jsoup.parser.HtmlTreeBuilder";
    static Set<String> watched() { return Set.of(TAG); }
    static void install(VirtualMachine vm, ReferenceType type) {
        if (!type.name().equals(TAG)) return;
        bind(type, "isEmpty", "()Z", 0, "entry");
        if (config.getProperty("mode").equals("original")) {
            bind(type, "isEmpty", "()Z", 11, "true");
            bind(type, "isEmpty", "()Z", 15, "false");
        }
    }
    static void thrown(ExceptionEvent event) { }
    static void hit(BreakpointEvent point, String phase) throws Exception {
        ThreadReference thread = point.thread();
        List<StackFrame> frames = thread.frames();
        if (frames.size() < 2) return;
        Location caller = frames.get(1).location();
        if (!caller.declaringType().name().equals(BUILDER) || !caller.method().name().equals("insertElementFor")
                || caller.codeIndex() != Long.parseLong(config.getProperty("consumerOffset"))) return;
        ObjectReference tag = frames.getFirst().thisObject();
        String name = ((StringReference)get(tag,"normalName")).value();
        if (!name.equals(config.getProperty("input"))) return;
        StackFrame publicCall = find(frames, config.getProperty("public"));
        StackFrame observer = find(frames, "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;");
        need(publicCall != null && observer != null, "wrong public clone consumer");
        ObjectReference parser = publicCall.thisObject();
        need(parser.equals(observer.getValue(observer.visibleVariableByName("clone"))), "wrong cloned parser");
        ObjectReference source = (ObjectReference)observer.getValue(observer.visibleVariableByName("original"));
        ObjectReference sourceSet = (ObjectReference)get(source,"tagSet"), set = (ObjectReference)get(parser,"tagSet");
        need(!set.equals(sourceSet), "aliased mutable tag sets");
        boolean inherits = sourceSet.equals(get(set,"source"));
        boolean fixed = config.getProperty("side").equals("new");
        need(inherits == fixed, "wrong live source registration");
        ObjectReference list = (ObjectReference)get(set,"customizers");
        if (fixed) {
            ObjectReference original = (ObjectReference)get(sourceSet,"customizers");
            need(list != null && !list.equals(original) && ((IntegerValue)get(list,"size")).value() == 1
                    && ((ArrayReference)get(list,"elementData")).getValue(0).equals(((ArrayReference)get(original,"elementData")).getValue(0)),
                    "callback identity or list differs");
        } else need(list == null, "unexpected inherited callback");
        ObjectReference element = (ObjectReference)frames.get(1).getValue(frames.get(1).visibleVariableByName("el"));
        need(tag.equals(get(element,"tag")), "predicate is for another element");
        Location at = point.location();
        need(hash(at.method().bytecodes()).equals(config.getProperty("code"))
                && hash(at.declaringType().constantPool()).equals(config.getProperty("pool")), "stale tag proof");
        int options = ((IntegerValue)get(tag,"options")).value(), mask = ((IntegerValue)get(at.declaringType(),"Void")).value();
        boolean result = (options & mask) != 0;
        if (phase.equals("entry")) {
            if (config.getProperty("mode").equals("original")) return;
            mark("applied",name,"" + options,"" + mask,"" + result,"" + inherits,site(caller));
            thread.forceEarlyReturn(point.virtualMachine().mirrorOf(result));
        } else {
            need(result == phase.equals("true"), "original branch disagrees");
            mark("original",name,"" + options,"" + mask,"" + result,"" + inherits,site(caller));
        }
    }
}
