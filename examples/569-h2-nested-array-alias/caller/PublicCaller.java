import java.sql.*;
import java.util.*;

public class PublicCaller {
    public static Integer[][] rows(String[][] input) {
        Integer[][] out = new Integer[input.length][];
        for (int i = 0; i < out.length; i++)
            out[i] = Arrays.stream(input[i]).map(Integer::valueOf).toArray(Integer[]::new);
        return out;
    }

    public static Integer[] identity(Integer[] v) {
        return v;
    }

    public static String inspect(Integer[][] v) {
        return Arrays.deepToString(v);
    }

    public static String observe(String[] a) throws Exception {
        try (var c = DriverManager.getConnection("jdbc:h2:mem:r32");
                var s = c.createStatement()) {
            if (a[0].equals("control")) {
                s.execute("CREATE ALIAS IDENTITY_ARRAY FOR \"PublicCaller.identity\"");
                try (var st = c.prepareStatement("SELECT IDENTITY_ARRAY(?)")) {
                    st.setObject(1, new Integer[] {1, 2});
                    try (var r = st.executeQuery()) {
                        r.next();
                        Object v = r.getObject(1);
                        return v.getClass().getSimpleName() + ":" + Arrays.toString((Object[]) v);
                    }
                }
            }
            s.execute("CREATE ALIAS F FOR \"PublicCaller.rows\"");
            boolean narrow = a[0].equals("challenge");
            String f =
                    "F("
                            + (narrow
                                    ? "ARRAY[ARRAY[1::BIGINT,2::BIGINT],ARRAY[3::BIGINT]]"
                                    : "ARRAY[ARRAY['1','2'],ARRAY['3']]")
                            + ")";
            String value;
            try (var r = s.executeQuery("SELECT " + f)) {
                r.next();
                Object[] v =
                        narrow
                                ? r.getObject(1, Short[][].class)
                                : r.getObject(1, Integer[][].class);
                value = v.getClass().getSimpleName() + ":" + Arrays.deepToString(v);
            }
            if (!narrow) return value;
            s.execute("CREATE ALIAS INSPECT FOR \"PublicCaller.inspect\"");
            try (var r = s.executeQuery("SELECT INSPECT(" + f + ")")) {
                r.next();
                return value + "/" + r.getString(1);
            }
        } catch (SQLException e) {
            return "sqlstate=" + e.getSQLState() + "/" + e.getClass().getSimpleName();
        }
    }
}
