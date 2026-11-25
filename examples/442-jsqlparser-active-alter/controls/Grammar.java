import java.sql.*;
import net.sf.jsqlparser.parser.AbstractJSqlParser.Dialect;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;

public class Grammar {
    static String parse(String sql) {
        try { return CCJSqlParserUtil.parse(sql, p -> p.withDialect(Dialect.POSTGRESQL)).toString(); }
        catch (net.sf.jsqlparser.JSQLParserException ex) { return ex.getClass().getSimpleName(); }
    }

    public static String observe(String[] args) throws Exception {
        String legal = "ALTER TABLE t ALTER COLUMN id TYPE INT USING id + 102";
        String tail = legal + " CASCADE";
        String url = "jdbc:postgresql://127.0.0.1:" + System.getenv("PUBLIC_COMPARISON_PG_PORT") + "/postgres";
        try (var c=DriverManager.getConnection(url, "postgres", System.getenv("PUBLIC_COMPARISON_PG_PASSWORD"));
             var s=c.createStatement()) {
            s.execute("CREATE TEMP TABLE t(id INT)");
            s.execute("INSERT INTO t VALUES (1)");
            String state;
            try { s.execute(tail); state="accepted"; }
            catch (SQLException ex) { state=ex.getSQLState(); }
            s.execute(legal);
            try (var rows=s.executeQuery("SELECT id FROM t")) {
                if (!rows.next()) throw new IllegalStateException("missing control row");
                return "with tail=" + parse(tail) + "/" + state + " without tail=" + parse(legal)
                        + "/id=" + rows.getInt(1) + " exhausted=" + !rows.next();
            }
        }
    }
}
