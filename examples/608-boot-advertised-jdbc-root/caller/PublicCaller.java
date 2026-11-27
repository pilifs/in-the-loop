import java.sql.Connection;
import java.sql.SQLException;
import javax.sql.DataSource;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.boot.jdbc.DataSourceUnwrapper;
import org.springframework.jdbc.datasource.AbstractDataSource;
import org.springframework.jdbc.datasource.DelegatingDataSource;

public class PublicCaller {
    static class Leaf extends AbstractDataSource {
        public Connection getConnection() { throw new UnsupportedOperationException(); }
        public Connection getConnection(String u, String p) { throw new UnsupportedOperationException(); }
    }
    static DataSource advertise(DataSource delegate, DataSource root) {
        return new DelegatingDataSource(delegate) {
            @Override public <T> T unwrap(Class<T> type) throws SQLException {
                return type.isInstance(root) ? type.cast(root) : super.unwrap(type);
            }
        };
    }
    static String derive(DataSource outer) {
        try (var pool = DataSourceBuilder.derivedFrom(outer).type(HikariDataSource.class).build()) {
            return pool.getJdbcUrl() + "/" + pool.getUsername();
        }
    }
    public static String observe(String[] args) {
        var leaf = new Leaf();
        if (args[0].equals("control")) return DataSourceUnwrapper.unwrapRoot(leaf) == leaf ? "same" : "other";
        try (var root = new HikariDataSource()) {
            root.setJdbcUrl("jdbc:h2:mem:root");
            root.setUsername("probe");
            var outer = advertise(leaf, root);
            if (args[0].equals("challenge")) return derive(outer) + ";" + derive(advertise(new Leaf(), root));
            DataSource selected = DataSourceUnwrapper.unwrapRoot(outer);
            return selected == root ? "root" : selected == leaf ? "delegate" : "other";
        }
    }
}
