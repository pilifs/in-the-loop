package inloop.p305;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;

import javax.servlet.http.HttpServletResponse;

import io.micrometer.core.instrument.Tag;
import org.springframework.boot.actuate.metrics.web.servlet.WebMvcTags;

/** 305's concrete control: it calls the original WebMvcTags.outcome(HttpServletResponse) of whichever actuator JAR is
 * on the class path, once per probe, and prints one JSON line per probe: the probe as given, the outcome as the JVM gave
 * it (the tag's key and value, or the exception's class), and how often the method called getStatus(). It decides
 * nothing; controls/oracle.py reads the lines. It maps, normalizes and replaces nothing, so the original bytecode
 * decides.
 *
 * <p>Each argument is {@code null} (a null response) or a status in decimal, which a carrier response reports. The
 * carrier is the test carrier the acceptance contract allows, its behaviour stated here: a
 * {@link java.lang.reflect.Proxy} of {@link HttpServletResponse} whose {@code getStatus()} returns the probe's int on
 * every call and counts the calls; every other method of the interface throws UnsupportedOperationException naming
 * the method, so a revision that called one would show an exception, not a silently invented value; {@code equals},
 * {@code hashCode} and {@code toString} are identity-based. It normalizes no status: {@code Integer.MIN_VALUE} reaches
 * the method as {@code Integer.MIN_VALUE}. {@code python3 -I controls/oracle.py argv} prints the arguments.
 *
 * <p>The tag is observed by value, its {@code getKey()} and {@code getValue()}; its identity is excluded on purpose
 * (claims/outcome-preservation.json). Compiled with {@code --release 21} against one actuator JAR, with
 * javax.servlet-api and micrometer-core; the method's descriptor is the same at both commits, so one driver JAR runs on
 * either. Only a RuntimeException is recorded as an outcome: an Error (an ExceptionInInitializerError among them) ends
 * the run, and the oracle reports the probes it lacks as an incomplete replay, never as a result. */
public final class OutcomeDriver {
    private OutcomeDriver() {
    }

    /** The carrier's invocation handler: one status, and the count of getStatus() calls. */
    static final class Carrier implements InvocationHandler {
        private final int status;
        private int getStatusCalls;

        Carrier(int status) {
            this.status = status;
        }

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            if (method.getDeclaringClass() == Object.class) {
                switch (method.getName()) {
                    case "equals":
                        return proxy == args[0];
                    case "hashCode":
                        return System.identityHashCode(proxy);
                    default:
                        return "carrier(" + this.status + ")";
                }
            }
            if (method.getName().equals("getStatus") && method.getParameterCount() == 0) {
                this.getStatusCalls++;
                return this.status;
            }
            throw new UnsupportedOperationException("the carrier implements only getStatus(): " + method);
        }
    }

    static String quote(String s) {
        if (s == null) {
            return "null";
        }
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                out.append('\\').append(c);
            } else if (c < 0x20) {
                out.append(String.format("\\u%04x", (int) c));
            } else {
                out.append(c);
            }
        }
        return out.append('"').toString();
    }

    public static void main(String[] args) {
        for (String arg : args) {
            Carrier carrier = null;
            HttpServletResponse response = null;
            if (!arg.equals("null")) {
                carrier = new Carrier(Integer.parseInt(arg));
                response = (HttpServletResponse) Proxy.newProxyInstance(OutcomeDriver.class.getClassLoader(),
                        new Class<?>[] {HttpServletResponse.class}, carrier);
            }
            String outcome;
            try {
                Tag tag = WebMvcTags.outcome(response);
                outcome = tag == null ? "\"returned\",\"key\":null,\"value\":null"
                        : "\"returned\",\"key\":" + quote(tag.getKey()) + ",\"value\":" + quote(tag.getValue());
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            String calls = carrier == null ? "null" : Integer.toString(carrier.getStatusCalls);
            System.out.println("{\"probe\":\"" + arg + "\",\"outcome\":" + outcome + ",\"getStatusCalls\":" + calls + "}");
        }
    }
}
