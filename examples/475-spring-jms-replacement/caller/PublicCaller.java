import java.lang.reflect.*;
import java.util.*;
import jakarta.jms.*;
import org.springframework.jms.connection.SingleConnectionFactory;

public class PublicCaller {
    final List<String> created = new ArrayList<>(), prepared = new ArrayList<>(), closed = new ArrayList<>();
    final Map<Session,String> tags = new IdentityHashMap<>();

    static <T> T proxy(Class<T> type, InvocationHandler handler) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, handler));
    }

    Connection physical() {
        String id = List.of("A","B","C").get(created.size());
        created.add(id);
        return proxy(Connection.class, (p,m,a) -> switch (m.getName()) {
            case "setExceptionListener" -> {
                if (!(a[0] instanceof ExceptionListener)) throw new AssertionError("missing provider listener");
                prepared.add(id);
                if (id.equals("B")) throw new JMSException("prepare-B");
                yield null;
            }
            case "close" -> { closed.add(id); yield null; }
            case "createSession" -> {
                if (closed.contains(id)) throw new JMSException("closed-" + id);
                var session = proxy(Session.class, (s,method,args) -> { throw new UnsupportedOperationException(method.getName()); });
                tags.put(session, "session-" + id);
                yield session;
            }
            case "toString" -> "connection-" + id;
            default -> throw new UnsupportedOperationException(m.getName());
        });
    }

    String session(Connection handle) throws JMSException {
        return tags.get(handle.createSession(false, Session.AUTO_ACKNOWLEDGE));
    }

    String run(String mode) throws JMSException {
        var cf = proxy(ConnectionFactory.class, (p,m,a) -> {
            if (m.getName().equals("createConnection")) return physical();
            throw new UnsupportedOperationException(m.getName());
        });
        var shared = new SingleConnectionFactory(cf);
        shared.setReconnectOnException(true);
        var first = shared.createConnection();
        String result;
        if (mode.equals("shared")) {
            result = "first=" + session(first) + " second=" + session(shared.createConnection());
        } else {
            String failure;
            try {
                if (mode.equals("reset")) { shared.resetConnection(); shared.createConnection(); }
                else shared.initConnection();
                failure = "returned";
            } catch (JMSException e) { failure = e.getMessage(); }
            String retry;
            try { retry = session(shared.createConnection()); }
            catch (JMSException e) { retry = e.getMessage(); }
            result = "failure=" + failure + " retry=" + retry;
        }
        return result + " created=" + created + " prepared=" + prepared + " closed=" + closed;
    }

    public static String observe(String[] args) throws JMSException { return new PublicCaller().run(args[0]); }
}
