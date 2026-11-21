import com.github.davidmoten.rx.jdbc.Database;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.List;

/** Run one observation in a new JVM. The JDBC query reads the committed rows independently. */
public final class Observe {
    public static void main(String[] args) throws Exception {
        String insert;
        if ("combined".equals(args[0])) {
            insert = "insert into note(text) values(?),(?)";
        } else if ("separate".equals(args[0])) {
            insert = "insert into note(text) values(?)";
        } else {
            throw new IllegalArgumentException(args[0]);
        }
        String url = "jdbc:h2:mem:calibration;DB_CLOSE_DELAY=-1";
        try (Connection c = DriverManager.getConnection(url); Statement sql = c.createStatement()) {
            sql.execute("create table note(id bigint auto_increment primary key, text varchar(255))");
        }
        Database db = Database.from(url);
        try {
            List<Integer> keys = db.update(insert).parameters("something", "again")
                    .returnGeneratedKeys().getAs(Integer.class).toList().toBlocking().single();
            System.out.println("keys=" + keys);
        } finally {
            db.close();
        }
        try (Connection c = DriverManager.getConnection(url); Statement sql = c.createStatement();
                ResultSet rs = sql.executeQuery("select id, text from note order by id")) {
            while (rs.next()) {
                System.out.println("row=" + rs.getLong(1) + "\t" + rs.getString(2));
            }
        }
        System.out.println("driver=" + org.h2.Driver.class.getProtectionDomain().getCodeSource().getLocation().getPath());
        System.out.println("client=" + Database.class.getProtectionDomain().getCodeSource().getLocation().getPath());
    }
}
