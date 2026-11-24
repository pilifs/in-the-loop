import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.*;

final class CaseFrames extends FrameValues {
    static final String V = "org.commonmark.renderer.html.CoreHtmlNodeRenderer$AltTextVisitor";
    static final String A = "org.commonmark.node.AbstractVisitor", CODE = "org.commonmark.node.Code";
    static final String DESC = "(Lorg/commonmark/node/Code;)V";
    static ObjectReference buffer, node;
    static String before, literal;
    static Set<String> watched() { return Set.of(V,A); }
    static void install(VirtualMachine vm, ReferenceType type) {
        if (!type.name().equals(config.getProperty("owner"))) return;
        bind(type,"visit",DESC,0,"entry");
        if (config.getProperty("mode").equals("original")) bind(type,"visit",DESC,Integer.parseInt(config.getProperty("exit")),"exit");
    }
    static void thrown(ExceptionEvent e) { }
    static String contents(ObjectReference sb) {
        int count = ((IntegerValue)get(sb,"count")).value();
        need(((ByteValue)get(sb,"coder")).value() == 0, "outside compact visitor buffer scope");
        StringBuilder text = new StringBuilder();
        for (Value cell : ((ArrayReference)get(sb,"value")).getValues(0,count)) text.append((char)(((ByteValue)cell).value() & 255));
        return text.toString();
    }
    static void hit(BreakpointEvent point, String phase) throws Exception {
        ThreadReference thread = point.thread();
        List<StackFrame> stack = thread.frames();
        StackFrame top = stack.getFirst();
        ObjectReference visitor = top.thisObject();
        if (!visitor.referenceType().name().equals(V)) return;
        need(find(stack,"org.commonmark.renderer.html.CoreHtmlNodeRenderer#visit(Lorg/commonmark/node/Image;)V") != null
                && find(stack,config.getProperty("public")) != null, "visitor outside the registered image renderer");
        Location at = point.location(), consumer = stack.get(1).location();
        need(id(consumer).equals(CODE + "#accept(Lorg/commonmark/node/Visitor;)V"), "wrong visitor dispatch");
        need(hash(at.method().bytecodes()).equals(config.getProperty("code"))
                && hash(at.declaringType().constantPool()).equals(config.getProperty("pool")), "stale visitor proof");
        boolean fixed = config.getProperty("side").equals("new");
        if (phase.equals("entry")) {
            node = (ObjectReference)top.getArgumentValues().getFirst();
            need(node.referenceType().name().equals(CODE) && node.equals(stack.get(1).thisObject())
                    && get(node,"firstChild") == null && get(node,"lastChild") == null, "outside the leaf Code scope");
            buffer = (ObjectReference)get(visitor,"sb");
            need(buffer.referenceType().name().equals("java.lang.StringBuilder"), "unexpected visitor buffer");
            before = contents(buffer);
            StringReference text = (StringReference)get(node,"literal");
            literal = text.value();
            if (config.getProperty("mode").equals("original")) return;
            String site = site(consumer);
            if (fixed) {
                Method append = buffer.referenceType().methodsByName("append","(Ljava/lang/String;)Ljava/lang/StringBuilder;").getFirst();
                Value returned = buffer.invokeMethod(thread,append,List.of(text),ObjectReference.INVOKE_SINGLE_THREADED);
                need(buffer.equals(returned), "different append receiver");
            }
            need(contents(buffer).equals(fixed ? before + literal : before), "incorrect application of visitor effect");
            mark("applied",literal,before,contents(buffer),site);
            thread.forceEarlyReturn(point.virtualMachine().mirrorOfVoid());
        } else {
            need(buffer.equals(get(visitor,"sb")) && contents(buffer).equals(fixed ? before + literal : before), "incorrect original visitor effect");
            mark("original",literal,before,contents(buffer),site(consumer));
        }
    }
}
