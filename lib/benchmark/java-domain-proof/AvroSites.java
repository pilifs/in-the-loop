package campaign;
import com.sun.jdi.*;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.*;

/** Actual binary reads and record lookups under the original public caller. */
public final class AvroSites {
    public static int input;
    public static int mode;
    static final String DEC = "org.apache.avro.io.BinaryDecoder";
    static final String REC = "org.apache.avro.generic.GenericData$Record";
    record Hit(int input, int mode, String owner, String argument, String caller, String hash) {}
    static final Map<Long,Hit> pending = new HashMap<>();

    static void calls(boolean capstone) throws Exception {
        Class<?> type=Class.forName(capstone?"campaign.DefaultReader":"campaign.EnumReader");
        Method entry=capstone ? type.getDeclaredMethod("check",int.class,boolean.class)
                              : type.getDeclaredMethod("read",int.class,String.class,String.class);
        entry.setAccessible(true);
        for (input=0; input<4; input++) for (mode=0; mode<(capstone?2:3); mode++) {
            Object result=capstone?entry.invoke(null,input,mode==0):entry.invoke(null,input,mode==2?"Other":"E",mode==1?"writer":"reader");
            System.out.println("ROW\t"+input+"\t"+mode+"\t"+result);
        }
    }
    static boolean selected(com.sun.jdi.Method m) {
        return (m.declaringType().name().equals(DEC) && m.name().equals("readInt") && m.signature().equals("()I"))
            || (m.declaringType().name().equals(REC) && m.name().equals("get")
                    && m.signature().equals("(Ljava/lang/String;)Ljava/lang/Object;"));
    }
    static void install(VirtualMachine vm, ReferenceType type) {
        List<com.sun.jdi.Method> methods=type.methods().stream().filter(AvroSites::selected).toList();
        if (methods.size()!=1) throw new IllegalStateException("unexpected original method count");
        var req=vm.eventRequestManager().createBreakpointRequest(methods.get(0).location());req.enable();
    }
    static int integer(Value v) { return ((IntegerValue)v).value(); }
    static Value field(ObjectReference r,String name) {return r.getValue(r.referenceType().fieldByName(name));}
    static String sha(byte[] b) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));
    }
    static void enter(BreakpointEvent e) throws Exception {
        var frames=e.thread().frames();String owner=e.location().declaringType().name();
        if (frames.stream().noneMatch(f->f.location().declaringType().name().equals("campaign.EnumReader")
                || f.location().declaringType().name().equals("campaign.DefaultReader"))) return;
        if (owner.equals(DEC) && frames.stream().noneMatch(f->f.location().declaringType().name().equals("org.apache.avro.generic.GenericDatumReader")
                && f.location().method().name().equals("read"))) return;
        var self=e.virtualMachine().classesByName("campaign.AvroSites").get(0);
        String argument;
        if (owner.equals(DEC)) {
            ObjectReference dec=frames.get(0).thisObject();int pos=integer(field(dec,"pos")), end=integer(field(dec,"limit"));
            argument=pos<end?String.valueOf(((ByteValue)((ArrayReference)field(dec,"buf")).getValue(pos)).value() & 255):"EOF";
        } else argument=((StringReference)frames.get(0).getArgumentValues().get(0)).value();
        Location caller=frames.get(1).location();var m=e.location().method();
        Hit hit=new Hit(integer(self.getValue(self.fieldByName("input"))),integer(self.getValue(self.fieldByName("mode"))),
                owner,argument,caller.declaringType().name()+"#"+caller.method().name()+caller.method().signature()+"@"+caller.codeIndex(),
                sha(m.bytecodes())+"/"+sha(m.declaringType().constantPool()));
        if (pending.put(e.thread().uniqueID(),hit)!=null) throw new IllegalStateException("nested selected method");
    }
    static void leave(MethodExitEvent e) {
        if (!selected(e.method())) return;
        Hit h=pending.remove(e.thread().uniqueID());if (h==null) return;
        Value v=e.returnValue();String result=v instanceof IntegerValue i?""+i.value():v==null?"null":v.type().name();
        System.out.println(String.join("\t","SITE",""+h.input(),""+h.mode(),h.owner(),h.argument(),result,h.caller(),h.hash()));
    }
    static void pipe(InputStream from,PrintStream to) {
        try {from.transferTo(to);} catch(IOException e){throw new UncheckedIOException(e);}
    }
    public static void main(String[] args) throws Exception {
        if(args[0].equals("calls")) {calls(args[1].equals("367"));return;}
        LaunchingConnector c=Bootstrap.virtualMachineManager().defaultConnector();var a=c.defaultArguments();
        a.get("main").setValue("campaign.AvroSites calls "+args[1]);
        a.get("options").setValue("-XX:ActiveProcessorCount=2 -Xmx384m -Djava.io.tmpdir=\""+args[3]+"\" -classpath \""+args[2]+"\"");
        VirtualMachine vm=c.launch(a);Process proc=vm.process();
        var out=Thread.startVirtualThread(()->pipe(proc.getInputStream(),System.out));var err=Thread.startVirtualThread(()->pipe(proc.getErrorStream(),System.err));
        try {
            if (!vm.canGetMethodReturnValues()) throw new IllegalStateException("method return visibility");
            for(String name:List.of(DEC,REC)) {
                var prep=vm.eventRequestManager().createClassPrepareRequest();prep.addClassFilter(name);prep.enable();
                var exits=vm.eventRequestManager().createMethodExitRequest();exits.addClassFilter(name);exits.enable();
                for(var t:vm.classesByName(name)) if(t.isPrepared()) install(vm,t);
            }
            boolean live=true;
            while(live) {
                EventSet set=vm.eventQueue().remove(45000);if(set==null)throw new IllegalStateException("trace stalled");
                for(Event e:set) {
                    if(e instanceof ClassPrepareEvent p)install(vm,p.referenceType());
                    if(e instanceof BreakpointEvent b)enter(b);
                    if(e instanceof MethodExitEvent x)leave(x);
                    if(e instanceof VMDisconnectEvent)live=false;
                }
                if(live)set.resume();
            }
        } catch(VMDisconnectedException ended) {
            // Exit status and the full input grid are checked on both traced and ordinary JVMs.
        } finally {
            if(proc.isAlive()&&!proc.waitFor(2,java.util.concurrent.TimeUnit.SECONDS))proc.destroyForcibly();
            out.join();err.join();if(proc.waitFor()!=0||!pending.isEmpty())throw new IllegalStateException("unfinished original call");
        }
    }
}
