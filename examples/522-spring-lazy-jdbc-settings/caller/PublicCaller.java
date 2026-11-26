import org.springframework.jdbc.datasource.*;

import java.lang.reflect.Proxy;
import java.sql.*;
import java.util.*;
import java.util.concurrent.Executor;

public class PublicCaller {
    static final Executor EXECUTOR = Runnable::run;

    static class Pool extends AbstractDataSource {
        int count;

        static class Session {
            int timeout;
            final TreeMap<String, String> info = new TreeMap<>();
        }

        Session last;

        public Connection getConnection(String u, String p) {
            return getConnection();
        }

        public Connection getConnection() {
            count++;
            Session session = new Session();
            last = session;
            var info = session.info;
            info.put("other", "driver");
            return (Connection)
                    Proxy.newProxyInstance(
                            getClass().getClassLoader(),
                            new Class[] {Connection.class},
                            (p, m, a) -> {
                                switch (m.getName()) {
                                    case "setClientInfo":
                                        if (a.length == 2) info.put((String) a[0], (String) a[1]);
                                        else {
                                            info.clear();
                                            ((Properties) a[0])
                                                    .forEach(
                                                            (k, v) ->
                                                                    info.put(
                                                                            (String) k,
                                                                            (String) v));
                                        }
                                        return null;
                                    case "getClientInfo":
                                        return info.get(a[0]);
                                    case "getNetworkTimeout":
                                        return session.timeout;
                                    case "setNetworkTimeout":
                                        session.timeout = (int) a[1];
                                        return null;
                                    case "getAutoCommit":
                                        return true;
                                    case "getTransactionIsolation":
                                        return Connection.TRANSACTION_READ_COMMITTED;
                                    case "isReadOnly":
                                        return false;
                                    case "close":
                                        return null;
                                    case "createStatement":
                                        return Proxy.newProxyInstance(
                                                getClass().getClassLoader(),
                                                new Class[] {Statement.class},
                                                (s, op, v) -> {
                                                    if (op.getName().equals("close")) return null;
                                                    throw new UnsupportedOperationException(
                                                            op.getName());
                                                });
                                    default:
                                        throw new UnsupportedOperationException(m.getName());
                                }
                            });
        }
    }

    static LazyConnectionDataSourceProxy proxy(Pool pool) {
        var ds = new LazyConnectionDataSourceProxy();
        ds.setTargetDataSource(pool);
        ds.setDefaultAutoCommit(true);
        ds.setDefaultTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
        ds.afterPropertiesSet();
        return ds;
    }

    public static String observe(String[] args) throws Exception {
        Pool pool = new Pool();
        var ds = proxy(pool);
        try (Connection a = ds.getConnection()) {
            if (args[0].equals("bulk")) {
                String read = a.getClientInfo("other");
                String first = pool.count + ":" + read;
                Pool other = new Pool();
                try (Connection b = proxy(other).getConnection()) {
                    Properties props = new Properties();
                    props.setProperty("bulk", "set");
                    b.setClientInfo(props);
                    return first + " / " + other.count + ":" + other.last.info;
                }
            }
            a.setClientInfo("app", "blue");
            int afterName = pool.count;
            if (args[0].equals("handles")) {
                a.setClientInfo("app", "green");
                try (Connection b = ds.getConnection()) {
                    b.setClientInfo("app", "red");
                }
                int before = pool.count;
                String value = a.getClientInfo("app");
                return "before="
                        + before
                        + " after="
                        + pool.count
                        + " value="
                        + value
                        + " other="
                        + a.getClientInfo("other");
            }
            a.setNetworkTimeout(EXECUTOR, 125);
            int afterTimeout = pool.count;
            int timeout = a.getNetworkTimeout(), afterGet = pool.count;
            try (var statement = a.createStatement()) {
                return afterName
                        + "/"
                        + afterTimeout
                        + "/"
                        + afterGet
                        + ":"
                        + timeout
                        + "/"
                        + pool.count
                        + ":"
                        + pool.last.info.get("app")
                        + ":"
                        + pool.last.timeout;
            }
        }
    }
}
