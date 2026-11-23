import com.sun.jdi.*;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/** Stop the original caller immediately before its read. Only the caller thread is suspended. */
public final class ObserveSchedule {
    public static void main(String[] args) throws Exception {
        String mode = args[0], classes = args[1];
        int line = Integer.parseInt(args[2]);
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        var config = connector.defaultArguments();
        config.get("main").setValue("MonitorLaunch " + mode);
        config.get("options").setValue("-ea -cp \"" + classes + "\"");
        VirtualMachine vm = connector.launch(config);
        Process child = vm.process();
        boolean observed = false;
        try {
            var prepare = vm.eventRequestManager().createClassPrepareRequest();
            prepare.addClassFilter("MonitorIdentity");
            prepare.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            prepare.enable();
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
            while (!observed && System.nanoTime() < deadline) {
                EventSet events = vm.eventQueue().remove(1000);
                if (events == null) continue;
                for (Event event : events) {
                    if (event instanceof ClassPrepareEvent loaded) {
                        var sites = loaded.referenceType().locationsOfLine(line);
                        if (sites.size() != 1 || !sites.get(0).method().name().equals("observe"))
                            throw new AssertionError("original read location");
                        var stop = vm.eventRequestManager().createBreakpointRequest(sites.get(0));
                        stop.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
                        stop.enable();
                    } else if (event instanceof BreakpointEvent stop) {
                        StackFrame caller = stop.thread().frame(0);
                        ThreadReference worker = (ThreadReference) caller.getValue(caller.visibleVariableByName("w"));
                        ReferenceType subject = stop.location().declaringType();
                        Field value = subject.fieldByName("shared");
                        var classLock = worker.referenceType().classObject();
                        boolean mixed = mode.equals("mixed");
                        boolean blockedOnClass = false;
                        int seen = -1;
                        while (System.nanoTime() < deadline) {
                            seen = ((IntegerValue) subject.getValue(value)).value();
                            if (mixed && seen == 6) break;
                            if (!mixed) {
                                worker.suspend();
                                try { blockedOnClass = classLock.equals(worker.currentContendedMonitor()); }
                                finally { worker.resume(); }
                                if (seen == 5 && blockedOnClass) break;
                            }
                            Thread.sleep(2);
                        }
                        if (mixed ? seen != 6 : seen != 5 || !blockedOnClass) throw new AssertionError("schedule not observed");
                        System.out.println(mode + " before the original read=" + seen + " workerBlockedOnClass=" + blockedOnClass);
                        observed = true;
                    }
                }
                events.resume();
            }
            if (!observed) throw new AssertionError("caller did not reach its read");
            try { vm.dispose(); } catch (VMDisconnectedException alreadyExited) {}
            if (!child.waitFor(10,TimeUnit.SECONDS) || child.exitValue()!=0) throw new AssertionError("original JVM exit");
            String result = new String(child.getInputStream().readAllBytes(),StandardCharsets.UTF_8).trim();
            if (!result.equals(mode.equals("mixed") ? "exposed" : "protected")) throw new AssertionError(result);
            System.out.println("original result=" + result);
        } finally { if (child.isAlive()) child.destroyForcibly(); }
    }
}
