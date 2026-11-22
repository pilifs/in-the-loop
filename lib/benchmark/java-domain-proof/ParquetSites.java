package campaign;

import com.sun.jdi.*;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Bind the actual wrapped array, read-only child, duplicated view and public return on a fresh JVM. */
public final class ParquetSites {
    static final String UTIL = "org.apache.parquet.variant.VariantUtil";
    static final String ROOT = "campaign.NestedBinary";
    static final String RO = "java.nio.HeapByteBufferR";
    static final String BUFFER = "java.nio.ByteBuffer";
    static final String GET = "(Ljava/nio/ByteBuffer;)Ljava/nio/ByteBuffer;";
    static final String DUP = "()Ljava/nio/ByteBuffer;";
    static final String WRAP = "([BII)Ljava/nio/ByteBuffer;";
    public static int input;
    record Wrap(long array, int start, int length, int capacity, String identity) {}
    record Child(ObjectReference source, int start, int end, String identity) {}
    static final Map<Integer,List<Wrap>> wraps = new HashMap<>();
    static Child child;
    static long duplicate;
    static String duplicateSite;

    static void calls() throws Exception {
        var entry = Class.forName(ROOT).getMethod("extent", int.class);
        for (input=0; input<64; input++) System.out.println("ROW\t"+input+"\t"+entry.invoke(null,input));
    }

    static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    static String site(Location l) throws Exception {
        Method m=l.method();
        return m.declaringType().name()+"#"+m.name()+m.signature()+"@"+l.codeIndex()+"/"+
               sha(m.bytecodes())+"/"+sha(m.declaringType().constantPool());
    }
    static int integer(Value v) { return ((IntegerValue)v).value(); }
    static Value field(ObjectReference ref,String name) { return ref.getValue(ref.referenceType().fieldByName(name)); }
    static int number(ObjectReference ref,String name) { return integer(field(ref,name)); }
    static void require(boolean condition,String message) {
        if (!condition) throw new IllegalStateException(message);
    }
    static int selector(VirtualMachine vm) {
        var self=vm.classesByName("campaign.ParquetSites");
        require(self.size()==1,"ambiguous campaign class");
        return integer(self.get(0).getValue(self.get(0).fieldByName("input")));
    }
    static void install(VirtualMachine vm,ReferenceType type) {
        String owner=type.name();
        String name=owner.equals(UTIL)?"getBinary":owner.equals(RO)?"duplicate":"wrap";
        String sig=owner.equals(UTIL)?GET:owner.equals(RO)?DUP:WRAP;
        var methods=type.methodsByName(name,sig);
        require(methods.size()==1 && methods.get(0).declaringType().equals(type),"ambiguous method "+owner);
        if (!owner.equals(UTIL)) require(type.classLoader()==null,"non-bootstrap buffer");
        var bp=vm.eventRequestManager().createBreakpointRequest(methods.get(0).location());
        bp.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD); bp.enable();
    }
    static void enter(BreakpointEvent e) throws Exception {
        Method target=e.location().method(); String owner=target.declaringType().name();
        var stack=e.thread().frames(); Location caller=stack.get(1).location();
        if (owner.equals(BUFFER)) {
            if (!caller.declaringType().name().equals(ROOT)||!caller.method().name().equals("rewrap")) return;
            var args=stack.get(0).getArgumentValues(); ArrayReference a=(ArrayReference)args.get(0);
            wraps.computeIfAbsent(selector(e.virtualMachine()),k->new ArrayList<>()).add(
                new Wrap(a.uniqueID(),integer(args.get(1)),integer(args.get(2)),a.length(),site(caller)+">"+site(e.location())));
        } else if (owner.equals(UTIL)) {
            require(child==null && caller.declaringType().name().equals("org.apache.parquet.variant.Variant")
                    && caller.method().name().equals("getBinary"),"unexpected public child entry");
            ObjectReference source=(ObjectReference)stack.get(0).getArgumentValues().get(0);
            require(source.referenceType().name().equals(RO) && source.referenceType().classLoader()==null,"unexpected child buffer");
            child=new Child(source,number(source,"position"),number(source,"limit"),site(caller)+">"+site(e.location()));
            duplicate=0; duplicateSite=null;
        } else if (child!=null && caller.declaringType().name().equals(UTIL) && caller.method().name().equals("slice")) {
            require(stack.get(2).location().method().name().equals("getBinary") &&
                    stack.get(0).thisObject().uniqueID()==child.source().uniqueID(),"other duplicate receiver");
            duplicateSite=site(caller)+">"+site(e.location());
        }
    }
    static void leave(MethodExitEvent e) {
        if (child==null) return;
        Method m=e.method();
        if (m.declaringType().name().equals(RO) && m.name().equals("duplicate") && m.signature().equals(DUP) && duplicateSite!=null) {
            require(duplicate==0,"second duplicate"); duplicate=((ObjectReference)e.returnValue()).uniqueID();
        }
        if (!m.declaringType().name().equals(UTIL) || !m.name().equals("getBinary") || !m.signature().equals(GET)) return;
        int code=selector(e.virtualMachine());
        List<Wrap> inputs=wraps.get(code); require(inputs!=null && inputs.size()==2,"value and metadata wraps");
        Wrap value=inputs.get(0), meta=inputs.get(1);
        ObjectReference view=(ObjectReference)e.returnValue();
        require(view.uniqueID()==duplicate && view.uniqueID()!=child.source().uniqueID() && view.referenceType().name().equals(RO)
                && ((ArrayReference)field(view,"hb")).uniqueID()==value.array() && ((ArrayReference)field(child.source(),"hb")).uniqueID()==value.array()
                && number(view,"capacity")==value.capacity() && number(view,"offset")==0
                && number(child.source(),"position")==child.start() && number(child.source(),"limit")==child.end(),"wrong backing or mutated cursor");
        System.out.println(String.join("\t","SITE",String.valueOf(code),""+value.start(),""+value.length(),""+value.capacity(),
                ""+meta.start(),""+meta.length(),""+meta.capacity(),""+child.start(),""+child.end(),""+number(view,"position"),
                ""+number(view,"limit"),value.identity(),meta.identity(),child.identity(),duplicateSite));
        child=null;
    }
    static void pipe(InputStream source,PrintStream dest) {
        try { source.transferTo(dest); } catch(IOException e) { throw new UncheckedIOException(e); }
    }
    public static void main(String[] args) throws Exception {
        if (args[0].equals("calls")) { calls(); return; }
        LaunchingConnector c=Bootstrap.virtualMachineManager().defaultConnector(); var a=c.defaultArguments();
        a.get("main").setValue("campaign.ParquetSites calls");
        a.get("options").setValue("-XX:ActiveProcessorCount=2 -Djava.io.tmpdir=\""+args[2]+"\" -classpath \""+args[1]+"\"");
        VirtualMachine vm=c.launch(a); Process process=vm.process();
        var out=Thread.startVirtualThread(()->pipe(process.getInputStream(),System.out));
        var err=Thread.startVirtualThread(()->pipe(process.getErrorStream(),System.err));
        try {
            require(vm.canGetMethodReturnValues(),"missing method return values");
            for (String type:List.of(UTIL,RO,BUFFER)) {
                var prep=vm.eventRequestManager().createClassPrepareRequest();prep.addClassFilter(type);prep.enable();
                for (ReferenceType loaded:vm.classesByName(type)) if (loaded.isPrepared()) install(vm,loaded);
                if (!type.equals(BUFFER)) {
                    var exits=vm.eventRequestManager().createMethodExitRequest();exits.addClassFilter(type);exits.enable();
                }
            }
            boolean live=true;
            while (live) {
                EventSet events=vm.eventQueue().remove(45000);require(events!=null,"trace stalled");
                for (Event e:events) {
                    if (e instanceof ClassPrepareEvent p) install(vm,p.referenceType());
                    if (e instanceof BreakpointEvent b) enter(b);
                    if (e instanceof MethodExitEvent x) leave(x);
                    if (e instanceof VMDisconnectEvent) live=false;
                }
                if (live) events.resume();
            }
        } catch (VMDisconnectedException normal) {
            // The controller also requires a normal process exit and all 64 bound rows.
        } finally {
            if (process.isAlive() && !process.waitFor(2,java.util.concurrent.TimeUnit.SECONDS)) process.destroyForcibly();
            out.join(); err.join();
            require(process.waitFor()==0 && child==null && wraps.size()==64,"incomplete JVM run");
        }
    }
}
