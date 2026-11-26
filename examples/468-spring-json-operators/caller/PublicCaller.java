import java.lang.reflect.*;
import java.sql.*;
import java.util.*;
import org.springframework.dao.InvalidDataAccessApiUsageException;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.datasource.AbstractDataSource;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

public class PublicCaller {
    static final Map<String,String> TITLE = Map.of("album","Back in Black");

    static String sql(String operator, String keys) {
        return "SELECT '[\"3\",\"11\"]'::jsonb " + operator + " '" + keys + "'::text[] AND :album = 'Back in Black'";
    }

    static <T> T proxy(Class<T> type, InvocationHandler handler) {
        return type.cast(Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, handler));
    }

    static class Recorder extends AbstractDataSource {
        String statement;
        int prepared, callbacks;
        final List<String> binds = new ArrayList<>();
        public Connection getConnection(String user, String password) { return getConnection(); }
        public Connection getConnection() {
            return proxy(Connection.class, (connection,m,a) -> switch (m.getName()) {
                case "prepareStatement" -> {
                    prepared++;
                    statement = (String)a[0];
                    yield proxy(PreparedStatement.class, (ps,method,params) -> switch (method.getName()) {
                        case "setString", "setObject" -> { binds.add(params[0] + "=" + params[1]); yield null; }
                        case "getWarnings", "close" -> null;
                        case "getConnection" -> connection;
                        default -> throw new UnsupportedOperationException(method.getName());
                    });
                }
                case "close" -> null;
                default -> throw new UnsupportedOperationException(m.getName());
            });
        }
    }

    static String recorded(String query) {
        var source = new Recorder();
        try {
            String returned = new NamedParameterJdbcTemplate(source).execute(query, TITLE, ps -> {
                source.callbacks++;
                return "sentinel";
            });
            return source.statement + " bind=" + source.binds + " callback=" + returned;
        } catch (InvalidDataAccessApiUsageException e) {
            return e.getClass().getSimpleName() + " prepared=" + source.prepared + " callback=" + source.callbacks;
        }
    }

    public static String observe(String[] args) {
        if (args[0].equals("mixed")) return recorded("SELECT :album = ?");
        if (args[0].equals("all")) return recorded(sql("?&","{3,11}"));
        String uri = "jdbc:postgresql://127.0.0.1:" + System.getenv("PUBLIC_COMPARISON_PG_PORT") + "/postgres";
        var db = new NamedParameterJdbcTemplate(new DriverManagerDataSource(uri, "postgres", System.getenv("PUBLIC_COMPARISON_PG_PASSWORD")));
        return recorded(sql("?|","{3,99}")) + " / " + recorded(sql("?&","{3,99}"))
                + " pgAny=" + db.queryForObject(sql("??|","{3,99}"),TITLE,Boolean.class)
                + " pgAll=" + db.queryForObject(sql("??&","{3,99}"),TITLE,Boolean.class);
    }
}
