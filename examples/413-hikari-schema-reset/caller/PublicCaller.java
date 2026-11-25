import java.sql.*;
import java.util.*;
import com.zaxxer.hikari.*;

public class PublicCaller {
    static String query(Connection c, String sql) throws SQLException {
        try (var stmt = c.createStatement(); var rows = stmt.executeQuery(sql)) {
            if (!rows.next()) throw new IllegalStateException("missing row");
            String value = rows.getString(1);
            if (rows.next()) throw new IllegalStateException("extra row");
            return value;
        }
    }
    public static String observe(String[] args) throws Exception {
        int port = Integer.parseInt(System.getenv("PUBLIC_COMPARISON_PG_PORT"));
        String password = System.getenv("PUBLIC_COMPARISON_PG_PASSWORD");
        String url = "jdbc:postgresql://127.0.0.1:" + port + "/postgres";
        // Each JVM owns a fresh private database inside the disposable server.
        String db = "caller_" + UUID.randomUUID().toString().replace("-", "");
        try (var admin = DriverManager.getConnection(url, "postgres", password); var stmt = admin.createStatement()) {
            stmt.execute("CREATE DATABASE " + db);
        }
        String fixture = "jdbc:postgresql://127.0.0.1:" + port + "/" + db;
        try (var setup = DriverManager.getConnection(fixture, "postgres", password); var stmt = setup.createStatement()) {
            stmt.execute("CREATE SCHEMA test");
            stmt.execute("CREATE TABLE test.pool_marker(n INTEGER)");
            stmt.execute("INSERT INTO test.pool_marker VALUES (37)");
        }
        var cfg = new HikariConfig();
        cfg.setJdbcUrl(fixture);
        cfg.setUsername("postgres");
        cfg.setPassword(password);
        cfg.setMinimumIdle(1);
        cfg.setMaximumPoolSize(1);
        cfg.setSchema("test");
        try (var pool = new HikariDataSource(cfg)) {
            String pid, state;
            try (var c = pool.getConnection()) {
                pid = query(c, "SELECT pg_backend_pid()");
                state = "first=" + c.getSchema();
                if (!args[0].equals("clean")) {
                    c.setSchema("invalid");
                    state += ", changed=" + c.getSchema();
                }
            }
            try (var c = pool.getConnection()) {
                state += ", second=" + c.getSchema() + ", sameBackend=" + pid.equals(query(c, "SELECT pg_backend_pid()"));
                if (args[0].equals("marker")) {
                    state += "; sql=" + query(c, "SELECT current_schema()");
                    try { state += ", rows=[" + query(c, "SELECT n FROM pool_marker") + "]"; }
                    catch (SQLException e) { state += ", SQLSTATE=" + e.getSQLState(); }
                }
                return state;
            }
        }
    }
}
