import java.sql.*;
import java.util.*;
import org.jooq.SQLDialect;
import org.jooq.conf.*;
import org.jooq.impl.DSL;
import static org.jooq.impl.DSL.*;

public class PublicCaller {
    public static String observe(String[] args) throws Exception {
        String[] rows = {"{\"id\":1,\"name\":\"Alice\"}", "{\"id\":2,\"name\":\"Bob\"}", "{\"id\":3,\"name\":\"Charlie\"}"};
        boolean partial = args[0].equals("partial");
        String json = "[" + String.join(",", partial ? List.of(rows[2], rows[0], rows[1]) : List.of(rows)) + "]";
        String port = System.getenv("PUBLIC_COMPARISON_PG_PORT");
        boolean postgres = port != null;
        try (Connection c = postgres ? DriverManager.getConnection("jdbc:postgresql://127.0.0.1:" + Integer.parseInt(port)
                + "/postgres", "postgres", System.getenv("PUBLIC_COMPARISON_PG_PASSWORD")) : DriverManager.getConnection("jdbc:h2:mem:caller")) {
            if (postgres) c.setAutoCommit(false);
            try (Statement init = c.createStatement()) { init.execute("CREATE TABLE \"TEST_TABLE\"(\"ID\" INT, \"NAME\" VARCHAR(100))"); }
            var mode = args[0].equals("prepared") ? StatementType.PREPARED_STATEMENT : StatementType.STATIC_STATEMENT;
            var ctx = DSL.using(c, postgres ? SQLDialect.POSTGRES : SQLDialect.H2, new Settings().withStatementType(mode));
            var loader = ctx.loadInto(table(name("TEST_TABLE")));
            var batched = partial ? loader.batchAfter(2) : loader.batchAll();
            var result = batched.loadJSON(json).fields(field(name("ID"), Integer.class), field(name("NAME"), String.class)).execute();
            var actual = new ArrayList<String>();
            try (var sql = c.createStatement(); var rs = sql.executeQuery("SELECT \"ID\",\"NAME\" FROM \"TEST_TABLE\" ORDER BY \"ID\",\"NAME\"")) {
                while (rs.next()) actual.add(rs.getInt(1) + "/" + rs.getString(2));
            }
            return "errors=" + result.errors().size() + " processed=" + result.processed() + " stored=" + result.stored() + "; " + actual;
        }
    }
}
