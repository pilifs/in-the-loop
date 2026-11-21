package calibration;

import com.github.davidmoten.rx.jdbc.Database;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;

public final class GeneratedKeys {
    /** Give each call its own H2 database, also when both sides run in one JVM. */
    public static int[] keys(boolean combined) throws SQLException {
        try (Connection connection = DriverManager.getConnection("jdbc:h2:mem:");
                Statement schema = connection.createStatement()) {
            schema.execute("create table note(id bigint auto_increment primary key, text varchar(255))");
            String sql = combined ? "insert into note(text) values(?),(?)" : "insert into note(text) values(?)";
            List<Integer> keys = Database.from(connection).update(sql).parameters("something", "again")
                    .returnGeneratedKeys().getAs(Integer.class).toList().toBlocking().single();
            int[] result = new int[keys.size()];
            for (int i = 0; i < result.length; i++) {
                result[i] = keys.get(i);
            }
            return result;
        }
    }
}
