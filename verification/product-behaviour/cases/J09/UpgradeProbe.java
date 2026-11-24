import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.sql.*;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import org.sqlite.core.NativeDB;

public class UpgradeProbe {
    private static void checkNativeImage() throws Exception {
        String resource = "/org/sqlite/native/Linux/x86_64/libsqlitejdbc.so";
        byte[] packaged;
        try (var bytes = NativeDB.class.getResourceAsStream(resource)) { packaged = bytes.readAllBytes(); }
        List<String> mapped = Files.readAllLines(Path.of("/proc/self/maps")).stream()
                .filter(line -> line.endsWith("libsqlitejdbc.so")).map(line -> line.substring(line.indexOf('/'))).distinct().toList();
        if (mapped.size() != 1) throw new AssertionError("expected one mapped sqlite native library, found " + mapped.size());
        var digest = MessageDigest.getInstance("SHA-256");
        if (!Arrays.equals(digest.digest(packaged), digest.digest(Files.readAllBytes(Path.of(mapped.get(0))))))
            throw new AssertionError("mapped native library differs from the production JAR");
    }
    public static String observe(String[] args) throws Exception {
        String rows = args[0].equals("nullable") ? "SELECT 0 AS k,NULL AS v UNION ALL SELECT 1,zeroblob(0) UNION ALL SELECT 2,zeroblob(5)"
                : "SELECT 0 AS k,NULL AS v UNION ALL SELECT 1,x'7f00' UNION ALL SELECT 2,zeroblob(5)";
        try (Connection db = DriverManager.getConnection("jdbc:sqlite::memory:"); Statement query = db.createStatement();
             ResultSet results = query.executeQuery("SELECT v FROM (" + rows + ") ORDER BY k " + (args[1].equals("reverse") ? "DESC" : "ASC"))) {
            checkNativeImage();
            StringBuilder history = new StringBuilder("native-matched");
            while (results.next()) {
                byte[] value = results.getBytes(1);
                boolean wasNull = results.wasNull();
                history.append('|').append(value == null ? "null" : value.length + ":" + HexFormat.of().formatHex(value)).append('/').append(wasNull);
            }
            return history.toString();
        }
    }
}
