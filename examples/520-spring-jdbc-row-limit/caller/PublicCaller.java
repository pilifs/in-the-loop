import org.springframework.jdbc.core.*;
import org.springframework.jdbc.datasource.*;

import java.lang.reflect.*;
import java.sql.*;
import java.util.*;

public class PublicCaller {
    static Object delegate(Method method, Object target, Object[] args) throws Throwable {
        try {
            return method.invoke(target, args);
        } catch (InvocationTargetException e) {
            throw e.getCause();
        }
    }

    static class IgnoresLimit extends AbstractDataSource {
        final List<Integer> settings = new ArrayList<>();

        public Connection getConnection(String user, String password) throws SQLException {
            return getConnection();
        }

        public Connection getConnection() throws SQLException {
            Connection real = DriverManager.getConnection("jdbc:h2:mem:rows", "sa", "");
            return (Connection)
                    Proxy.newProxyInstance(
                            getClass().getClassLoader(),
                            new Class[] {Connection.class},
                            (p, m, a) -> {
                                Object value = delegate(m, real, a);
                                if (!m.getName().equals("createStatement")) return value;
                                return Proxy.newProxyInstance(
                                        getClass().getClassLoader(),
                                        new Class[] {Statement.class},
                                        (s, op, params) -> {
                                            if (op.getName().equals("setMaxRows")) {
                                                settings.add((Integer) params[0]);
                                                return null;
                                            }
                                            return delegate(op, value, params);
                                        });
                            });
        }
    }

    public static String observe(String[] args) {
        var source = new IgnoresLimit();
        var jdbc = new JdbcTemplate(source);
        if (!args[0].equals("default")) jdbc.setMaxRows(args[0].equals("two") ? 2 : 0);
        String sql = "SELECT v FROM (VALUES (11),(22),(33)) AS rows_(v) ORDER BY v";
        RowMapper<Integer> mapper = (r, i) -> r.getInt(1);
        List<Integer> list = jdbc.query(sql, mapper), callbacks = new ArrayList<>();
        jdbc.query(sql, (RowCallbackHandler) r -> callbacks.add(r.getInt(1)));
        try (var stream = jdbc.queryForStream(sql, mapper)) {
            return list + "/" + callbacks + "/" + stream.toList() + " set=" + source.settings;
        }
    }
}
