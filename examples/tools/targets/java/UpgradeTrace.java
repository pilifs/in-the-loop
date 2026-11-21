import com.sun.jdi.Bootstrap;
import com.sun.jdi.Location;
import com.sun.jdi.Method;
import com.sun.jdi.ObjectReference;
import com.sun.jdi.ReferenceType;
import com.sun.jdi.StackFrame;
import com.sun.jdi.VirtualMachine;
import com.sun.jdi.VMDisconnectedException;
import com.sun.jdi.connect.Connector;
import com.sun.jdi.connect.LaunchingConnector;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.HashSet;
import java.util.Set;

/** Observe an actual entry in the child JVM launched here. The class files on its classpath are untouched. */
public final class UpgradeTrace {
    private static Thread forward(InputStream input, OutputStream output) {
        Thread thread = new Thread(() -> {
            try {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        });
        thread.start();
        return thread;
    }

    private static String quote(String value) {
        if (value.contains("\"")) throw new IllegalArgumentException("unrepresentable launcher argument");
        return "\"" + value + "\"";
    }

    private static void breakpoint(VirtualMachine vm, ReferenceType type, String name, String descriptor, String purpose) {
        for (Method method : type.methodsByName(name, descriptor)) {
            if (!method.declaringType().equals(type) || method.isAbstract() || method.isNative()) continue;
            BreakpointRequest point = vm.eventRequestManager().createBreakpointRequest(method.location());
            point.putProperty("purpose", purpose);
            point.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            point.enable();
        }
    }

    private static void install(VirtualMachine vm, ReferenceType type, String owner, String method,
                                String descriptor, String exception) {
        if (type.name().equals(owner)) breakpoint(vm, type, method, descriptor, "entry");
        if (exception.isEmpty()) return;
        if (type.name().equals(exception)) {
            ExceptionRequest request = vm.eventRequestManager().createExceptionRequest(type, true, true);
            request.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            request.enable();
        }
        if (type.name().equals("UpgradeObservation"))
            breakpoint(vm, type, "writeFailure", "(Ljava/io/BufferedWriter;Ljava/lang/Throwable;)V", "failure");
    }

    private static void watch(VirtualMachine vm, String name) {
        ClassPrepareRequest prepare = vm.eventRequestManager().createClassPrepareRequest();
        prepare.addClassFilter(name);
        prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);
        prepare.enable();
    }

    // A Java Throwable can have its stack replaced. Snapshot the actual throwing thread and
    // retain only events below observe(). The catcher selects the escaping object by JDI identity.
    private static List<String> throwingStack(ExceptionEvent event, String observer, String entry,
                                               Set<Long> sites) throws Exception {
        List<String> result = new ArrayList<>();
        Location catcher = event.catchLocation();
        boolean caughtBelow = false, escapesEntry = false;
        for (StackFrame frame : event.thread().frames()) {
            Location location = frame.location();
            ReferenceType type = location.declaringType();
            Method method = location.method();
            String member = type.name() + "#" + method.name() + method.signature();
            if (member.indexOf('\t') >= 0 || member.indexOf('\r') >= 0 || member.indexOf('\n') >= 0)
                return null;
            if (member.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) {
                result.add("observer\t" + location.codeIndex());
                if (escapesEntry && sites.contains(location.codeIndex())) result.add("escape\t" + entry);
                return result;
            }
            // An exception caught inside the selected call has not crossed its boundary.
            // A finally block that rethrows it generates another event for the same object.
            if (catcher != null && method.equals(catcher.method())) caughtBelow = true;
            if (member.equals(entry) && !caughtBelow) escapesEntry = true;
            // A class loaded by two class loaders cannot be attributed by a name in the JVM load log.
            if (event.virtualMachine().classesByName(type.name()).size() == 1)
                result.add(member + "\t" + location.codeIndex() + "\t" + location.lineNumber());
        }
        return null;
    }

    private static String invocation(BreakpointEvent hit, String observer, Set<Long> sites) throws Exception {
        String dispatched = null;
        for (StackFrame frame : hit.thread().frames()) {
            Method method = frame.location().method();
            String name = method.declaringType().name() + "#" + method.name() + method.signature();
            if (name.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) {
                long pc = frame.location().codeIndex();
                return dispatched != null && sites.contains(pc) ? pc + "\t" + dispatched : null;
            }
            dispatched = name;
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        String entry = args[0];
        int hash = entry.indexOf('#'), paren = entry.indexOf('(', hash);
        String owner = entry.substring(0, hash);
        String method = entry.substring(hash + 1, paren);
        String descriptor = entry.substring(paren);
        String observer = args[5], exception = args[6];
        Set<Long> sites = new HashSet<>();
        for (String index : args[4].split(",")) sites.add(Long.parseLong(index));
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        Map<String, Connector.Argument> launch = connector.defaultArguments();
        launch.get("home").setValue(args[1]);
        launch.get("options").setValue("-Xmx384m -Duser.timezone=UTC -Duser.language=en -Duser.country=US "
                + quote("-Djava.io.tmpdir=" + args[2]) + " " + quote("-Duser.home=" + args[2])
                + " " + quote("-Dupgrade.observation.file=" + Paths.get(args[2], "observation.txt"))
                + " -verbose:class -cp " + quote(args[3]));
        StringBuilder main = new StringBuilder("UpgradeObservation ").append(quote(observer));
        for (String argument : Arrays.copyOfRange(args, 7, args.length)) main.append(' ').append(quote(argument));
        launch.get("main").setValue(main.toString());
        launch.get("suspend").setValue("true");
        VirtualMachine vm = connector.launch(launch);
        Process child = vm.process();
        OutputStream diagnostics = Files.newOutputStream(Paths.get(args[2], "child.stderr"));
        Thread stdout = forward(child.getInputStream(), System.out), stderr = forward(child.getErrorStream(), diagnostics);
        String entryInvocation = null;
        boolean finished = false;
        Map<String, List<String>> thrown = new LinkedHashMap<>();
        try {
            List<String> watched = exception.isEmpty() ? Arrays.asList(owner)
                    : Arrays.asList(owner, exception, "UpgradeObservation");
            for (String name : watched) {
                watch(vm, name);
                for (ReferenceType type : vm.classesByName(name))
                    if (type.isPrepared()) install(vm, type, owner, method, descriptor, exception);
            }
            while (!finished) {
                EventSet events = vm.eventQueue().remove();
                for (Event event : events) {
                    if (event instanceof ClassPrepareEvent) {
                        install(vm, ((ClassPrepareEvent) event).referenceType(), owner, method, descriptor, exception);
                    } else if (event instanceof ExceptionEvent) {
                        ExceptionEvent raised = (ExceptionEvent) event;
                        if (!raised.exception().referenceType().name().equals(exception)) continue;
                        String id = raised.thread().uniqueID() + "/" + raised.exception().uniqueID();
                        List<String> stack = throwingStack(raised, observer, entry, sites);
                        if (stack != null) {
                            // try-with-resources and finally can rethrow the very same object
                            // from the caller after the library's frame has been unwound.
                            List<String> eventsForObject = thrown.remove(id);
                            if (eventsForObject == null) eventsForObject = new ArrayList<>();
                            if (thrown.size() == 64) thrown.remove(thrown.keySet().iterator().next());
                            if (eventsForObject.size() < 512) {
                                eventsForObject.add("event");
                                eventsForObject.addAll(stack);
                            } else if (!eventsForObject.get(eventsForObject.size() - 1).equals("truncated")) {
                                eventsForObject.add("truncated");
                            }
                            thrown.put(id, eventsForObject);
                        }
                    } else if (event instanceof BreakpointEvent) {
                        BreakpointEvent point = (BreakpointEvent) event;
                        if ("failure".equals(point.request().getProperty("purpose"))) {
                            ObjectReference escaping = (ObjectReference) point.thread().frame(0).getArgumentValues().get(1);
                            List<String> stack = thrown.get(point.thread().uniqueID() + "/" + escaping.uniqueID());
                            if (stack != null && escaping.referenceType().name().equals(exception))
                                System.err.println("UPGRADE-THROW-STACK " + Base64.getEncoder().encodeToString(
                                        String.join("\n", stack).getBytes(StandardCharsets.UTF_8)));
                        } else if (vm.classesByName(owner).size() == 1 && vm.classesByName(observer).size() == 1) {
                            String site = invocation(point, observer, sites);
                            if (site != null) {
                                entryInvocation = site;
                                point.request().disable();
                            }
                        }
                    } else if (event instanceof VMDisconnectEvent) {
                        finished = true;
                    }
                }
                if (!finished) events.resume();
            }
        } catch (VMDisconnectedException e) {
            // A normal child shutdown can disconnect after VMDeath before the next queue read.
            finished = true;
        } finally {
            if (!finished && child.isAlive()) child.destroy();
            stdout.join();
            stderr.join();
            diagnostics.close();
        }
        int status = child.waitFor();
        if (entryInvocation != null) {
            System.err.println("UPGRADE-HIT " + entry);
            System.err.println("UPGRADE-CALL-SITE " + entryInvocation);
        }
        System.exit(status);
    }
}
