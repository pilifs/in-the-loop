import java.io.*;
import java.nio.charset.StandardCharsets;
import java.sql.*;
import java.util.*;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.jdbc.datasource.init.*;

public class PublicCaller {
    static final String URL = "jdbc:h2:mem:scripts;DB_CLOSE_DELAY=-1";
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("descriptor")) {
            try { return ScriptUtils.readScript(new LineNumberReader(new StringReader("select 1;")), "--", ";"); }
            catch (NoSuchMethodError e) { return e.getClass().getSimpleName(); }
        }
        String sql;
        try (var input = PublicCaller.class.getResourceAsStream("/org/springframework/jdbc/datasource/init/test-data-with-multi-line-nested-comments.sql")) {
            sql = new String(Objects.requireNonNull(input).readAllBytes(), StandardCharsets.UTF_8);
        }
        if (args[0].equals("bare")) sql = sql.replaceFirst("(?m)^-{2,}\\*/", "*/");
        if (args[0].equals("sentinel"))
            sql = sql.replace("-- This is also a comment.", "-- discarded */ INSERT INTO users VALUES('sentinel','row');");
        String status = "ok";
        try (var c = DriverManager.getConnection(URL); var s = c.createStatement()) {
            s.execute("create table users(first_name varchar(60), last_name varchar(60))");
            try { new ResourceDatabasePopulator(new ByteArrayResource(sql.getBytes(StandardCharsets.UTF_8))).populate(c); }
            catch (ScriptException e) { status = e.getClass().getSimpleName(); }
        }
        var rows = new ArrayList<String>();
        try (var c = DriverManager.getConnection(URL); var s = c.createStatement();
             var rs = s.executeQuery("select first_name,last_name from users order by first_name")) {
            while (rs.next()) rows.add(rs.getString(1) + " " + rs.getString(2));
        }
        return status + " rows=" + rows;
    }
}
