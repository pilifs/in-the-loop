import java.sql.*;
import java.util.*;

public class PublicCaller {
    static String elements(Object[] a) {
        List<Integer> values = new ArrayList<>();
        for (Object v : a) values.add((Integer) v);
        values.sort(Comparator.nullsFirst(Integer::compareTo));
        return values.toString();
    }

    static String array(ResultSet r) throws Exception {
        if (!r.next()) throw new AssertionError("missing aggregate");
        String s =
                elements(r.getObject(1, Integer[].class))
                        + "/"
                        + elements((Object[]) r.getArray(1).getArray());
        if (r.next()) throw new AssertionError("extra row");
        return s;
    }

    public static String observe(String[] a) throws Exception {
        try (var c = DriverManager.getConnection("jdbc:h2:mem:r31")) {
            String source = " FROM UNNEST(ARRAY[CAST(? AS INTEGER), CAST(? AS INTEGER)]) T(V)";
            if (a[0].equals("control"))
                try (var s = c.createStatement();
                        var r =
                                s.executeQuery(
                                        "SELECT ARRAY_AGG(V) FROM UNNEST(ARRAY[1,2]) T(V)")) {
                    return array(r);
                }
            try (var agg = c.prepareStatement("SELECT ARRAY_AGG(V)" + source);
                    var rows = c.prepareStatement("SELECT V" + source)) {
                List<String> results = new ArrayList<>();
                for (int[] pair :
                        a[0].equals("intent")
                                ? new int[][] {{1, 2}}
                                : new int[][] {{7, 7}, {-4, 9}}) {
                    for (var st : List.of(agg, rows)) {
                        st.setInt(1, pair[0]);
                        st.setInt(2, pair[1]);
                    }
                    try (var r = agg.executeQuery()) {
                        String value = array(r);
                        if (a[0].equals("challenge"))
                            try (var plain = rows.executeQuery()) {
                                List<Integer> v = new ArrayList<>();
                                while (plain.next()) v.add(plain.getObject(1, Integer.class));
                                Collections.sort(v);
                                value += "/" + v;
                            }
                        results.add(value);
                    }
                }
                return String.join(" / ", results);
            }
        }
    }
}
