import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.*;
import java.util.Properties;
import org.relique.jdbc.csv.CsvDriver;

public final class ReferenceAPI {
    private static long read(int n, boolean timestamp) throws Exception {
        Path dir = Files.createTempDirectory("csv-reader");
        Path table = dir.resolve("items.csv");
        try {
            Files.writeString(table, "id,stamp\n7," + (2020 + n) + "-12-06 11:52:21\n");
            Properties p = new Properties();
            p.setProperty("columnTypes", "Int,Timestamp");
            p.setProperty("timestampFormat", "uuuu-MM-dd HH:mm:ss");
            p.setProperty("timeZoneName", "UTC");
            p.setProperty("useDateTimeFormatter", "true");
            try (Connection c = new CsvDriver().connect("jdbc:relique:csv:" + dir, p);
                 Statement s = c.createStatement();
                 ResultSet rows = s.executeQuery("SELECT id, stamp FROM items")) {
                if (!rows.next()) throw new AssertionError();
                return timestamp ? rows.getTimestamp(2).toLocalDateTime().getYear() : rows.getInt(1);
            }
        } finally {
            Files.deleteIfExists(table);
            Files.deleteIfExists(dir);
        }
    }
    public static long primary(int n) throws Exception { return read(n, true); }
    public static long control(int n) throws Exception { return read(n, false); }
}
