import java.lang.reflect.*;
import java.sql.*;
import java.util.*;
import javax.sql.DataSource;
import org.springframework.jdbc.core.namedparam.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.*;
import org.springframework.jdbc.support.GeneratedKeyHolder;

public class PublicCaller {
    static Object forward(Object target, Method m, Object[] args) throws Throwable {
        try { return m.invoke(target, args); } catch (InvocationTargetException e) { throw e.getCause(); }
    }

    static <T> T proxy(Class<T> type, InvocationHandler handler) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, handler));
    }

    static class Recording extends DelegatingDataSource {
        final List<String> bindings = new ArrayList<>();
        final List<List<Object>> batches = new ArrayList<>();
        Recording(DataSource source) { super(source); }

        @Override public Connection getConnection() throws SQLException {
            Connection c = super.getConnection();
            if (!c.getAutoCommit()) throw new SQLException("fixture requires auto-commit for the independent read");
            return proxy(Connection.class, (p, method, args) -> {
                Object result = forward(c, method, args);
                if (!method.getName().equals("prepareStatement")) return result;
                var statement = (PreparedStatement)result;
                var parameters = new TreeMap<Integer,Object>();
                return proxy(PreparedStatement.class, (s,m,a) -> {
                    Object value = forward(statement, m, a);
                    if ((m.getName().equals("setString") || m.getName().equals("setObject")) && a[0] instanceof Integer index) {
                        bindings.add(index + "=" + a[1]);
                        parameters.put(index, a[1]);
                    }
                    if (m.getName().equals("addBatch")) batches.add(List.copyOf(parameters.values()));
                    return value;
                });
            });
        }
    }

    public static String observe(String[] args) throws SQLException {
        var physical = new DriverManagerDataSource("jdbc:h2:mem:batch;DB_CLOSE_DELAY=-1", "sa", "");
        var ds = new Recording(physical);
        boolean indexed = args[0].equals("keys");
        try (var conn = physical.getConnection(); var s = conn.createStatement()) {
            s.execute("CREATE TABLE custmr(id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, forename VARCHAR(16), country VARCHAR(8))");
        }
        var holder = new GeneratedKeyHolder();
        if (indexed) {
            int[] counts = JdbcClient.create(ds).sql("INSERT INTO custmr(forename) VALUES (?)")
                    .batch().param("foo").add().param("bar").add().update(holder,"id");
            var keys = new ArrayList<Long>();
            for (var entry : holder.getKeyList()) keys.add(((Number)entry.values().iterator().next()).longValue());
            var names = new ArrayList<String>();
            try (var reader = physical.getConnection(); var select = reader.prepareStatement("SELECT forename FROM custmr WHERE id=?");
                 var tally = reader.createStatement()) {
                for (long key : keys) {
                    select.setLong(1,key);
                    try (var result = select.executeQuery()) { while (result.next()) names.add(result.getString(1)); }
                }
                try (var total = tally.executeQuery("SELECT COUNT(*) FROM custmr")) {
                    total.next();
                    return "bind=" + ds.bindings + " counts=" + Arrays.toString(counts) + " distinctKeys="
                            + new HashSet<>(keys).size() + " read=" + names + " rows=" + total.getInt(1);
                }
            }
        }
        var jdbc = new NamedParameterJdbcTemplate(ds);
        var rows = new MapSqlParameterSource[]{new MapSqlParameterSource("forename","foo").addValue("country","UK"),
                new MapSqlParameterSource("forename","bar").addValue("country","US")};
        String sql = "INSERT INTO custmr(forename,country) VALUES (:forename,:country)";
        int[] counts = args[0].equals("named") ? jdbc.batchUpdate(sql, rows, holder) : jdbc.batchUpdate(sql,rows);
        return "bind=" + ds.bindings + " rows=" + ds.batches + " counts=" + Arrays.toString(counts);
    }
}
