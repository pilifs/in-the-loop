import java.sql.Connection;
import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.jdbc.datasource.DelegatingDataSource;
import org.springframework.jdbc.datasource.LazyConnectionDataSourceProxy;

public class PublicCaller {
    static HikariDataSource derive(DataSource source, String user, String password) {
        return (HikariDataSource) DataSourceBuilder.derivedFrom(source).username(user).password(password).build();
    }
    static int query(DataSource source) throws Exception {
        try (var pool = derive(source, "sa", ""); var con = pool.getConnection(); var stmt = con.createStatement();
             var rows = stmt.executeQuery("select marker from proof_row")) {
            if (!rows.next()) throw new AssertionError("missing marker");
            int marker = rows.getInt(1);
            if (rows.next()) throw new AssertionError("extra row");
            return marker;
        }
    }
    public static String observe(String[] args) throws Exception {
        String url = "jdbc:h2:mem:derived";
        try (var root = new HikariDataSource()) {
            root.setJdbcUrl(url);
            root.setUsername("sa");
            root.setPassword("");
            var lazy = new LazyConnectionDataSourceProxy(root);
            if (args[0].equals("challenge")) {
                try (var keep = root.getConnection(); var stmt = keep.createStatement()) {
                    stmt.executeUpdate("create table proof_row(marker integer)");
                    stmt.executeUpdate("insert into proof_row values(73)");
                    return query(lazy) + "/" + query(new DelegatingDataSource(lazy));
                }
            }
            DataSource source = args[0].equals("control") ? root : lazy;
            try (var derived = derive(source, "migration", "fixture")) {
                return url.equals(derived.getJdbcUrl()) + ":" + derived.getUsername() + ":" + derived.getPassword()
                        + ":" + ("sa".equals(root.getUsername()) && "".equals(root.getPassword()));
            }
        }
    }
}
