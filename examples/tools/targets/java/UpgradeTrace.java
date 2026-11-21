import com.sun.jdi.Bootstrap;
import com.sun.jdi.Method;
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
import java.util.Arrays;
import java.util.Map;

/** Observe an actual entry in the child JVM launched here. The class files on its classpath are untouched. */
public final class UpgradeTrace {
    private static Thread forward(InputStream input) {
        Thread thread = new Thread(() -> {
            try {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) != -1) System.out.write(buffer, 0, count);
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

    private static void install(VirtualMachine vm, ReferenceType type, String name, String descriptor) {
        for (Method method : type.methodsByName(name, descriptor)) {
            if (!method.declaringType().equals(type) || method.isAbstract() || method.isNative()) continue;
            BreakpointRequest point = vm.eventRequestManager().createBreakpointRequest(method.location());
            point.setSuspendPolicy(EventRequest.SUSPEND_EVENT_THREAD);
            point.enable();
        }
    }

    private static boolean calledFromObserver(BreakpointEvent hit, String observer, String via) throws Exception {
        boolean sawVia = via.isEmpty();
        for (StackFrame frame : hit.thread().frames()) {
            Method method = frame.location().method();
            String name = method.declaringType().name() + "#" + method.name() + method.signature();
            if (name.equals(via)) sawVia = true;
            if (name.equals(observer + "#observe([Ljava/lang/String;)Ljava/lang/String;")) return sawVia;
        }
        return false;
    }

    public static void main(String[] args) throws Exception {
        String entry = args[0];
        int hash = entry.indexOf('#'), paren = entry.indexOf('(', hash);
        String owner = entry.substring(0, hash);
        String method = entry.substring(hash + 1, paren);
        String descriptor = entry.substring(paren);
        LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
        Map<String, Connector.Argument> launch = connector.defaultArguments();
        launch.get("home").setValue(args[1]);
        launch.get("options").setValue("-Xmx384m -Duser.timezone=UTC -Duser.language=en -Duser.country=US "
                + quote("-Djava.io.tmpdir=" + args[2]) + " " + quote("-Duser.home=" + args[2])
                + " -verbose:class -cp " + quote(args[3]));
        StringBuilder main = new StringBuilder("UpgradeObservation");
        for (String argument : Arrays.copyOfRange(args, 5, args.length)) main.append(' ').append(quote(argument));
        launch.get("main").setValue(main.toString());
        launch.get("suspend").setValue("true");
        VirtualMachine vm = connector.launch(launch);
        Process child = vm.process();
        Thread stdout = forward(child.getInputStream()), stderr = forward(child.getErrorStream());
        boolean hit = false, finished = false;
        try {
            ClassPrepareRequest prepare = vm.eventRequestManager().createClassPrepareRequest();
            prepare.addClassFilter(owner);
            prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);
            prepare.enable();
            for (ReferenceType type : vm.classesByName(owner))
                if (type.isPrepared()) install(vm, type, method, descriptor);
            while (!finished) {
                EventSet events = vm.eventQueue().remove();
                for (Event event : events) {
                    if (event instanceof ClassPrepareEvent) {
                        install(vm, ((ClassPrepareEvent) event).referenceType(), method, descriptor);
                    } else if (event instanceof BreakpointEvent) {
                        BreakpointEvent point = (BreakpointEvent) event;
                        if (calledFromObserver(point, args[5], args[4])) {
                            hit = true;
                            point.request().disable();
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
        }
        int status = child.waitFor();
        if (hit) System.err.println("UPGRADE-HIT " + entry);
        System.exit(status);
    }
}
