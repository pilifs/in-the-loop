package campaign;

import com.sun.jdi.*;
import com.sun.jdi.event.*;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Observe the result on the operand stack of the original Schema.validateName caller through JDI method exits. */
public final class NamePolicySites {
    static final String SCHEMA = "org.apache.avro.Schema";
    final boolean legacy;
    boolean bound;

    NamePolicySites(boolean legacy) { this.legacy = legacy; }

    void observe(MethodExitEvent event) throws Exception {
        if (!event.method().name().equals("get") || !event.method().signature().equals("()Ljava/lang/Object;")) return;
        List<StackFrame> frames = event.thread().frames();
        if (frames.size() < 2) return;
        StackFrame consumer = frames.get(1);
        Location site = consumer.location();
        if (!site.declaringType().name().equals(SCHEMA) || !site.method().name().equals("validateName")) return;
        if (site.codeIndex() != 3 || !site.method().signature().equals("(Ljava/lang/String;)Ljava/lang/String;"))
            throw new IllegalStateException("unexpected name-policy call site");
        String adapter = legacy ? "campaign.EnumReader" : "campaign.DefaultReader";
        List<String> entries = legacy ? List.of("renamed", "preserved") : List.of("union", "direct");
        List<String> callers = frames.stream().map(StackFrame::location).filter(l -> l.declaringType().name().equals(adapter)
                && entries.contains(l.method().name()) && l.method().signature().equals("(I)I")).map(l -> l.method().name()).toList();
        if (callers.isEmpty()) return;
        if (callers.size() != 1) throw new IllegalStateException("ambiguous public entry");
        if (!bound) {
            System.out.println("SITE\t" + AvroSites.sha(site.method().bytecodes()) + "\t" + AvroSites.sha(site.declaringType().constantPool()));
            bound = true;
        }
        ReferenceType owner = event.virtualMachine().classesByName(legacy ? "java.lang.Boolean" : "org.apache.avro.NameValidator").get(0);
        Value expected = owner.getValue(owner.fieldByName(legacy ? "TRUE" : "UTF_VALIDATOR"));
        if (expected == null || !expected.equals(event.returnValue())) throw new IllegalStateException("different policy in public reader");
        ReferenceType harness = event.virtualMachine().classesByName("campaign.NameChecks").get(0);
        int code = AvroSites.integer(harness.getValue(harness.fieldByName("selector")));
        String name = ((StringReference) consumer.getArgumentValues().get(0)).value();
        System.out.println("GET\t" + callers.get(0) + "\t" + code + "\t" + name + "\t" + expected.type().name());
    }

    public static void main(String[] args) throws Exception {
        var connector = Bootstrap.virtualMachineManager().defaultConnector();
        var launch = connector.defaultArguments();
        launch.get("main").setValue("campaign.NameChecks " + args[0] + " " + args[1] + " public");
        launch.get("options").setValue("-XX:ActiveProcessorCount=2 -Xmx384m -Djava.io.tmpdir=\"" + args[3] + "\" -cp \"" + args[2] + "\"");
        VirtualMachine vm = connector.launch(launch);
        Process proc = vm.process();
        var stdout = Thread.startVirtualThread(() -> AvroSites.pipe(proc.getInputStream(), System.out));
        var stderr = Thread.startVirtualThread(() -> AvroSites.pipe(proc.getErrorStream(), System.err));
        var tracer = new NamePolicySites(args[0].equals("364"));
        try {
            if (!vm.canGetMethodReturnValues() || !vm.canGetBytecodes() || !vm.canGetConstantPool())
                throw new IllegalStateException("missing debugger capability");
            var prepare = vm.eventRequestManager().createClassPrepareRequest();
            prepare.addClassFilter(SCHEMA);
            prepare.enable();
            boolean live = true;
            while (live) {
                EventSet events = vm.eventQueue().remove(45000);
                if (events == null) throw new IllegalStateException("name-policy trace stalled");
                for (Event e : events) {
                    if (e instanceof ClassPrepareEvent) {
                        var exits = vm.eventRequestManager().createMethodExitRequest();
                        exits.addClassFilter("java.lang.ThreadLocal");
                        exits.enable();
                    } else if (e instanceof MethodExitEvent exit) tracer.observe(exit);
                    else if (e instanceof VMDisconnectEvent) live = false;
                }
                if (live) events.resume();
            }
        } catch (VMDisconnectedException finished) {
            // The exit status and the complete set of public input rows are checked below and by the job.
        } finally {
            if (!proc.waitFor(2, TimeUnit.SECONDS)) proc.destroyForcibly();
            stdout.join();
            stderr.join();
            if (proc.waitFor() != 0 || !tracer.bound) throw new IllegalStateException("incomplete name-policy trace");
        }
    }
}
