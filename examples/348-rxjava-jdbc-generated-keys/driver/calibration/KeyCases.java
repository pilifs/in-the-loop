package calibration;

import com.github.davidmoten.rx.jdbc.Database;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;

/** Compare the adapter to a real subscriber and read committed rows over a separate JDBC connection. */
public final class KeyCases {
    public static void main(String[] args) throws Exception {
        for (String shape : args) {
            boolean combined = "combined".equals(shape);
            if (!combined && !"separate".equals(shape)) throw new IllegalArgumentException(shape);
            String url = "jdbc:h2:mem:control_" + shape;
            try (Connection anchor = DriverManager.getConnection(url); Statement sql = anchor.createStatement()) {
                sql.execute("create table note(id bigint auto_increment primary key, text varchar(255))");
                String insert = combined ? "insert into note(text) values(?),(?)" : "insert into note(text) values(?)";
                Database db = Database.from(url);
                List<Integer> direct;
                try {
                    direct = db.update(insert).parameters("something", "again").returnGeneratedKeys()
                            .getAs(Integer.class).toList().toBlocking().single();
                } finally {
                    db.close();
                }
                List<String> rows = new ArrayList<>();
                try (ResultSet rs = sql.executeQuery("select id,text from note order by id")) {
                    while (rs.next()) {
                        String encoded = Base64.getEncoder().encodeToString(rs.getString(2).getBytes(StandardCharsets.UTF_8));
                        rows.add("[" + rs.getLong(1) + ",\"" + encoded + "\"]");
                    }
                }
                System.out.println("{\"shape\":\"" + shape + "\",\"direct\":" + direct + ",\"rows\":" + rows
                        + ",\"adapter\":" + Arrays.toString(GeneratedKeys.keys(combined)) + "}");
            }
        }
    }
}
