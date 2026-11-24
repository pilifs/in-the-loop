import java.nio.file.Path;
import java.sql.*;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        boolean spill = args[0].equals("spill");
        String url = "jdbc:h2:" + Path.of("reports").toAbsolutePath() + ";MAX_MEMORY_ROWS=" + (spill ? 1 : 100000);
        String values = args[1].equals("permuted") ? "('Abc'),('z'),('ABC'),('abc'),('abc')" : "('abc'),('ABC'),('Abc'),('abc'),('z')";
        String type = args[1].equals("case-sensitive") ? "VARCHAR" : "VARCHAR_IGNORECASE";
        try (Connection db = DriverManager.getConnection(url); Statement sql = db.createStatement()) {
            sql.execute("CREATE TABLE input_rows(v " + type + ")");
            sql.execute("INSERT INTO input_rows VALUES " + values);
            sql.execute("CREATE TABLE report AS SELECT v FROM input_rows ORDER BY v");
        }
        try (Connection db = DriverManager.getConnection(url); Statement sql = db.createStatement()) {
            int distinct;
            try (ResultSet count = sql.executeQuery("SELECT COUNT(DISTINCT v) FROM input_rows")) { count.next(); distinct = count.getInt(1); }
            List<String> spellings = new ArrayList<>();
            try (ResultSet rows = sql.executeQuery("SELECT v FROM report")) { while (rows.next()) spellings.add(rows.getString(1)); }
            Collections.sort(spellings);
            return distinct + "/" + String.join(",", spellings);
        }
    }
}
