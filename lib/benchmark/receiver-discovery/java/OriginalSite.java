import com.sun.jdi.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** Observe a user-supplied input on unmodified classes with JDI breakpoints and exception events. */
public final class OriginalSite {
    static String at(Location l) { return l == null ? "uncaught" : l.declaringType().name() + "#" + l.method().name() + l.method().signature() + "@" + l.codeIndex(); }
    static String quote(String s) {
        if (s.indexOf('"') >= 0 || s.indexOf('\n') >= 0) throw new IllegalArgumentException("quoted launcher argument");
        return "\"" + s + "\"";
    }
    public static void main(String[] args) throws Exception {
        // classpath, site class, method, descriptor, PC, step-branch, entry class, method, descriptor, primitive args
        var launcher = Bootstrap.virtualMachineManager().defaultConnector();
        var params = launcher.defaultArguments();
        params.get("options").setValue("-ea -Xverify:all -cp " + quote(args[0]));
        StringBuilder main = new StringBuilder("org.intheloop.observation.CallOnce ").append(quote(args[1]));
        for (int i=6; i<args.length; i++) main.append(' ').append(quote(args[i]));
        params.get("main").setValue(main.toString());
        VirtualMachine vm = launcher.launch(params);
        var process = vm.process();
        try {
            var manager = vm.eventRequestManager();
            var prepared = manager.createClassPrepareRequest(); prepared.addClassFilter(args[1]); prepared.enable();
            var throwsEvent = manager.createExceptionRequest(null,true,true); throwsEvent.addClassFilter(args[1]); throwsEvent.enable();
            if (args[5].equals("return")) {
                var exits = manager.createMethodExitRequest(); exits.addClassFilter(args[1]); exits.enable();
            }
            String site = args[1] + "#" + args[2] + args[3] + "@" + args[4];
            int bindings = 0;
            boolean done = false;
            while (!done) {
                EventSet events = vm.eventQueue().remove(30000);
                if (events == null) throw new IllegalStateException("JDI event timeout");
                for (Event event : events) {
                    if (event instanceof ClassPrepareEvent e) {
                        List<Method> methods = e.referenceType().methodsByName(args[2],args[3]);
                        if (methods.size() != 1) throw new IllegalStateException("original method binding");
                        Location target = methods.get(0).locationOfCodeIndex(Long.parseLong(args[4]));
                        if (target == null || !at(target).equals(site)) throw new IllegalStateException("original PC binding");
                        manager.createBreakpointRequest(target).enable(); bindings++;
                    } else if (event instanceof BreakpointEvent e) {
                        System.out.println("hit " + at(e.location()));
                        if (args[5].equals("branch")) {
                            var step = manager.createStepRequest(e.thread(),StepRequest.STEP_MIN,StepRequest.STEP_INTO);
                            step.addCountFilter(1); step.enable();
                        }
                    } else if (event instanceof StepEvent e) {
                        System.out.println("next " + at(e.location())); manager.deleteEventRequest(e.request());
                    } else if (event instanceof ExceptionEvent e && at(e.location()).equals(site)) {
                        System.out.println("raised " + e.exception().referenceType().name() + " caught " + at(e.catchLocation()));
                    } else if (event instanceof MethodExitEvent e && at(e.location()).equals(site)) {
                        System.out.println("return-value " + e.returnValue());
                    } else if (event instanceof VMDeathEvent || event instanceof VMDisconnectEvent) done = true;
                }
                if (!done) events.resume();
            }
            if (process.waitFor() != 0) throw new IllegalStateException(new String(process.getErrorStream().readAllBytes(), StandardCharsets.UTF_8));
            System.out.print(new String(process.getInputStream().readAllBytes(),StandardCharsets.UTF_8));
            if (bindings != 1) throw new IllegalStateException("original class bindings: " + bindings);
        } finally { if (process.isAlive()) process.destroyForcibly(); }
    }
}
