import com.sun.jdi.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;

/** Follow the resource stream returned in the subject to the actual Properties.load
 * receiver and each positive refill of the pinned JDK LineReader. No subject method is invoked. */
final class PropertyLoadTrace {
    private static final String PROPS = "java.util.Properties", LINE = PROPS + "$LineReader";
    private final VirtualMachine vm;
    private final EventRequestManager requests;
    private final List<String> events;
    private final List<EventRequest> installed = new ArrayList<>();
    private final Map<EventRequest, Pending> exits = new HashMap<>();
    private final Map<ObjectReference,String> sources = new HashMap<>();
    private final Map<ObjectReference,Properties> parsed = new HashMap<>();
    private final Map<ClassLoaderReference,Integer> loaders = new HashMap<>();
    private final Set<ObjectReference> getters = new HashSet<>();
    private ThreadReference root;
    private Pending lookup, load, opening;
    private static final class Pending {
        String kind, descriptor, caller, locator, archive, entry, decoder;
        int depth;
        ObjectReference receiver;
        ObjectReference argument, zipStream;
        boolean eof;
        final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        final StringBuilder chars = new StringBuilder();
    }

    PropertyLoadTrace(VirtualMachine vm, List<String> events) {
        this.vm = vm; this.requests = vm.eventRequestManager(); this.events = events;
    }
    private static String q(String s) { return ObservedInitializer.text(s); }
    private static String digest(byte[] b) throws Exception { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b)); }
    private static byte[] units(String text) {
        var b=java.nio.ByteBuffer.allocate(2*text.length());
        for (int i=0;i<text.length();i++) b.putChar(text.charAt(i));
        return b.array();
    }
    private static Value field(ObjectReference object,String key) {
        Field f=object.referenceType().fieldByName(key);
        if (f==null) throw new IllegalStateException("missing bound JDK field " + object.referenceType().name() + "." + key);
        return object.getValue(f);
    }
    private static String string(Value value) { return ((StringReference)value).value(); }
    private static String site(Location at) { return at.declaringType().name()+"#"+at.method().name()+at.method().signature()+"@"+at.codeIndex(); }
    private void enable(EventRequest r, String kind) {
        r.putProperty("property-read",kind); r.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
        r.enable(); installed.add(r);
    }
    private void bp(ReferenceType type,String name,String desc,String kind,ObjectReference receiver) {
        Method m=type.methodsByName(name,desc).stream().filter(x -> x.declaringType().equals(type)).findFirst().orElseThrow();
        BreakpointRequest r=requests.createBreakpointRequest(m.location());
        r.addThreadFilter(root);
        if (receiver!=null) r.addInstanceFilter(receiver);
        enable(r,kind);
    }
    private void install(ReferenceType t) {
        if (t.classLoader()!=null) return;
        switch (t.name()) {
            case "java.lang.Class" -> bp(t,"getResourceAsStream","(Ljava/lang/String;)Ljava/io/InputStream;","lookup",null);
            case "java.util.zip.ZipFile" -> bp(t,"getInputStream","(Ljava/util/zip/ZipEntry;)Ljava/io/InputStream;","zip",null);
            case "java.io.FileInputStream" -> bp(t,"<init>","(Ljava/io/File;)V","open",null);
            case PROPS -> {
                bp(t,"load","(Ljava/io/InputStream;)V","stream",null);
                bp(t,"load","(Ljava/io/Reader;)V","reader",null);
            }
            case LINE -> {
                ModificationWatchpointRequest r=requests.createModificationWatchpointRequest(t.fieldByName("inLimit"));
                r.addThreadFilter(root); enable(r,"refill");
            }
        }
    }
    void begin(ThreadReference thread) {
        root=thread;
        for (String name:List.of("java.lang.Class","java.util.zip.ZipFile","java.io.FileInputStream",PROPS,LINE)) {
            ClassPrepareRequest prepare=requests.createClassPrepareRequest();
            prepare.addClassFilter(name); prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL); enable(prepare,"prepare");
            for (ReferenceType t:vm.classesByName(name)) if (t.isPrepared()) install(t);
        }
        ExceptionRequest errors=requests.createExceptionRequest(null,true,true);
        errors.addThreadFilter(thread);enable(errors,"failure");
    }
    private void endRequest(EventRequest r) { requests.deleteEventRequest(r); installed.remove(r); exits.remove(r); }
    private static boolean wraps(ObjectReference stream,ObjectReference original) {
        Set<Long> seen=new HashSet<>();
        while (stream!=null && seen.add(stream.uniqueID())) {
            if (stream.equals(original)) return true;
            Field inner=stream.referenceType().allFields().stream().filter(f->f.declaringType().name().equals("java.io.FilterInputStream") && f.name().equals("in")).findFirst().orElse(null);
            if (inner==null) break;
            stream=(ObjectReference)stream.getValue(inner);
        }
        return false;
    }

    private void enter(BreakpointEvent e,String kind) throws Exception {
        StackFrame frame=root.frame(0);
        Location caller=root.frame(1).location();
        if (kind.equals("zip") && lookup==null || kind.equals("key") && load!=null) return;
        if (!kind.equals("zip") && !kind.equals("open") && caller.declaringType().classLoader()==null) return;
        if (kind.equals("open") && caller.declaringType().classLoader()==null
                && (root.frameCount()<3 || root.frame(2).location().declaringType().classLoader()==null)) return;
        Pending c=new Pending(); c.kind=kind;c.descriptor=e.location().method().signature();c.depth=root.frameCount();c.caller=site(caller);
        ObjectReference receiver=frame.thisObject();
        c.receiver=receiver;
        Value arg=frame.getArgumentValues().get(0);
        if (kind.equals("lookup")) {
            if (lookup!=null) throw new IllegalStateException("nested application resource lookup");
            lookup=c;
            ReferenceType owner=((ClassObjectReference)receiver).reflectedType();
            ClassLoaderReference cl=owner.classLoader();
            if (cl==null) throw new IllegalStateException("unregistered bootstrap resource lookup");
            String requested=string(arg);
            c.entry=requested.startsWith("/") ? requested.substring(1) : owner.name().substring(0,owner.name().lastIndexOf('.')+1).replace('.','/')+requested;
            ObjectReference parent=(ObjectReference)field(cl,"parent");
            c.locator="\"api\":\"Class.getResourceAsStream\",\"owner\":"+q(owner.name())+",\"name\":"+q(requested)
                    +",\"loaderClass\":"+q(cl.referenceType().name())+",\"delegatesTo\":"+(parent==null?"null":q(parent.referenceType().name()))
                    +",\"loader\":"+loaders.computeIfAbsent(cl,ignored->loaders.size());
        } else if (kind.equals("zip")) {
            c.archive=string(field(receiver,"name"));c.entry=string(field((ObjectReference)arg,"name"));
            if (!lookup.entry.equals(c.entry)) return;
        } else if (kind.equals("open")) {
            if (opening!=null || arg==null) return;
            opening=c; c.locator=string(field((ObjectReference)arg,"path"));
        } else if (kind.equals("key")) {
            if (!parsed.containsKey(c.receiver)) return;
            c.locator=string(arg);
        } else {
            if (load!=null || arg==null) throw new IllegalStateException("null or nested properties load");
            load=c; c.argument=(ObjectReference)arg;
            ObjectReference stream=c.argument;
            if (kind.equals("reader")) {
                if (!stream.referenceType().name().equals("java.io.InputStreamReader")) throw new IllegalStateException("unbound Reader implementation");
                ObjectReference decoder=(ObjectReference)field(stream,"sd");
                ObjectReference charset=(ObjectReference)field(decoder,"cs");
                c.decoder=string(field(charset,"name"));
                stream=(ObjectReference)field(decoder,"in");
            }
            c.locator=sources.get(stream);
            if (c.locator==null && stream.referenceType().name().equals("java.io.FileInputStream")) {
                c.locator="\"api\":\"FileInputStream\",\"path\":"+q(string(field(stream,"path")));
            }
            if (c.locator==null) throw new IllegalStateException("unbound Properties.load stream "+stream.referenceType().name());
            if (getters.add(c.receiver)) bp(e.location().declaringType(),"getProperty","(Ljava/lang/String;)Ljava/lang/String;","key",receiver);
            if (parsed.containsKey(c.receiver)) throw new IllegalStateException("load onto an already observed properties table");
            // Unrepresented pre-existing entries or defaults can change the meaning of parsed keys.
            if (!receiver.referenceType().name().equals(PROPS) || field(receiver,"defaults")!=null)
                throw new IllegalStateException("properties file is being loaded into a nonstandard table");
            ObjectReference map=(ObjectReference)field(receiver,"map");
            if (((LongValue)field(map,"baseCount")).value()!=0 || field(map,"counterCells")!=null)
                throw new IllegalStateException("properties file needs a newly empty target table");
        }
        MethodExitRequest exit=requests.createMethodExitRequest();
        exit.addClassFilter(e.location().declaringType());exit.addThreadFilter(root);
        enable(exit,"return");exits.put(exit,c);
    }

    private void refill(ModificationWatchpointEvent e) throws Exception {
        if (load==null || !e.location().method().name().equals("readLine")) return;
        boolean bytes=load.kind.equals("stream");
        if (!load.argument.equals(field(e.object(),bytes?"inStream":"reader"))) throw new IllegalStateException("different stream at properties refill");
        int n=((IntegerValue)e.valueToBe()).value();
        if (n==-1) { load.eof=true;return; }
        if (n<1 || load.eof || load.bytes.size()+load.chars.length()+n>1048576) throw new IllegalStateException("unsupported partial properties refill");
        ArrayReference b=(ArrayReference)field(e.object(),bytes?"inByteBuf":"inCharBuf");
        for (Value v:b.getValues(0,n)) {
            if (bytes) load.bytes.write(((ByteValue)v).value()); else load.chars.append(((CharValue)v).value());
        }
    }
    private void parsed(Pending c,String thrown,String where) throws Exception {
        boolean bytes=c.kind.equals("stream");
        byte[] consumed=bytes?c.bytes.toByteArray():units(c.chars.toString());
        Properties result=new Properties();
        String failure=null;
        try {
            if (bytes) result.load(new ByteArrayInputStream(consumed)); else result.load(new StringReader(c.chars.toString()));
        } catch (IllegalArgumentException invalid) { failure=invalid.getClass().getName(); }
        if (!Objects.equals(thrown,failure)) throw new IllegalStateException("JDK Properties parser did not reproduce the actual outcome");
        List<byte[]> pairs=new ArrayList<>();
        for (var entry:result.entrySet()) pairs.add(ObservedInitializer.tablePair((String)entry.getKey(),(String)entry.getValue()));
        pairs.sort(Arrays::compareUnsigned);
        events.add("{\"operation\":\"load\",\"descriptor\":"+q(c.descriptor)+",\"source\":{"+c.locator+"},\"decoder\":"+q(bytes?"ISO-8859-1":c.decoder)
                +",\"units\":"+(bytes?consumed.length:c.chars.length())+",\"consumedSha256\":"+q(digest(consumed))+",\"eof\":"+c.eof
                +",\"parsedEntries\":"+pairs.size()+",\"parsedSha256\":"+q(ObservedInitializer.tableDigest(pairs))
                +",\"threw\":"+(thrown==null?"null":q(thrown))+",\"site\":"+q(where)+",\"caller\":"+q(c.caller)+"}");
        if (thrown==null) parsed.put(c.receiver,result);
        load=null;
    }
    private void returned(MethodExitEvent e) throws Exception {
        Pending c=exits.get(e.request());
        String name=switch(c.kind) {case "lookup"->"getResourceAsStream";case "zip"->"getInputStream";case "open"->"<init>";case "key"->"getProperty";default->"load";};
        if (!e.method().name().equals(name) || !e.method().signature().equals(c.descriptor) || root.frameCount()!=c.depth) return;
        endRequest(e.request());
        if (c.kind.equals("lookup")) {
            ObjectReference result=(ObjectReference)e.returnValue();
            if (result!=null) {
                if (c.zipStream==null || !wraps(result,c.zipStream)) throw new IllegalStateException("lookup return does not wrap the selected JAR entry stream");
                c.locator+=",\"archive\":"+q(c.archive)+",\"entry\":"+q(c.entry);
                sources.put(result,c.locator);
            }
            events.add("{\"operation\":\"lookup\","+c.locator+",\"present\":"+(result!=null)+",\"caller\":"+q(c.caller)+"}");
            lookup=null;
        } else if (c.kind.equals("zip")) {
            if (lookup.zipStream!=null) throw new IllegalStateException("ambiguous JAR streams in one resource lookup");
            lookup.zipStream=(ObjectReference)e.returnValue();lookup.archive=c.archive;lookup.entry=c.entry;
        } else if (c.kind.equals("open")) opening=null;
        else if (c.kind.equals("key")) {
            String actual=e.returnValue()==null?null:string(e.returnValue());
            if (!Objects.equals(actual,parsed.get(c.receiver).getProperty(c.locator))) throw new IllegalStateException("parsed value disagrees at original getProperty");
            events.add("{\"operation\":\"getProperty\",\"keySha256\":"+q(digest(units(c.locator)))+",\"valueSha256\":"
                    +(actual==null?"null":q(digest(units(actual))))+",\"caller\":"+q(c.caller)+"}");
        } else parsed(c,null,site(e.location()));
    }
    private void failed(ExceptionEvent e) throws Exception {
        if (e.catchLocation()==null || e.catchLocation().declaringType().classLoader()==null) return;
        String thrown=e.exception().referenceType().name();
        Pending failed=null;
        if (load!=null && thrown.equals("java.lang.IllegalArgumentException")) { failed=load;parsed(load,thrown,site(e.location())); }
        else if (opening!=null && thrown.equals("java.io.FileNotFoundException")) {
            failed=opening;
            events.add("{\"operation\":\"open\",\"path\":"+q(opening.locator)+",\"threw\":"+q(thrown)+",\"site\":"+q(site(e.location()))+"}");
            opening=null;
        }
        if (failed!=null) {
            for (var request:List.copyOf(exits.keySet())) if (exits.get(request)==failed) endRequest(request);
        }
    }
    boolean handle(Event event) throws Exception {
        if (event.request()==null || !(event.request().getProperty("property-read") instanceof String kind)) return false;
        if (event instanceof ClassPrepareEvent e) install(e.referenceType());
        else if (event instanceof BreakpointEvent e) enter(e,kind);
        else if (event instanceof ModificationWatchpointEvent e) refill(e);
        else if (event instanceof MethodExitEvent e) returned(e);
        else if (event instanceof ExceptionEvent e) failed(e);
        return true;
    }
    void finish() {
        if (!exits.isEmpty() || lookup!=null || load!=null || opening!=null) throw new IllegalStateException("incomplete properties operation");
        requests.deleteEventRequests(installed);
    }
}
