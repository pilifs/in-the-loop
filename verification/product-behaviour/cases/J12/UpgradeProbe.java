import java.sql.*;
import java.lang.reflect.Array;
import java.util.*;
import java.util.function.Consumer;
import org.apache.calcite.runtime.Hook;

public class UpgradeProbe {
    private static String values(Object value, boolean ordered) throws Exception {
        if (value instanceof java.sql.Array) value = ((java.sql.Array)value).getArray();
        List<Integer> numbers = new ArrayList<>();
        if (value instanceof Collection) {
            for (Object element : (Collection<?>)value) numbers.add(((Number)element).intValue());
        } else {
            for (int i=0; i<Array.getLength(value); i++) numbers.add(((Number)Array.get(value, i)).intValue());
        }
        if (!ordered) Collections.sort(numbers);
        return numbers.toString();
    }
    public static String observe(String[] args) throws Exception {
        boolean unordered = !args[0].equals("ordered"), ordered = !args[0].equals("unordered");
        String projection = (unordered ? ", COLLECT(n) AS u" : "") + (ordered ? ", COLLECT(n) WITHIN GROUP (ORDER BY n DESC) AS o" : "");
        String rows = args[1].equals("original") ? "(10,1),(20,7),(10,3),(10,3),(10,2)" : "(10,2),(10,3),(20,7),(10,1),(10,3)";
        List<String> generated = new ArrayList<>();
        try (Connection db = DriverManager.getConnection("jdbc:calcite:"); Statement query = db.createStatement();
             Hook.Closeable listener = Hook.JAVA_PLAN.addThread((Consumer<String>) generated::add);
             ResultSet result = query.executeQuery("SELECT dept" + projection + " FROM (VALUES " + rows + ") AS t(dept,n) GROUP BY dept ORDER BY dept")) {
            StringJoiner output = new StringJoiner("|");
            while (result.next()) {
                int col = 1;
                StringBuilder row = new StringBuilder().append(result.getInt(col++));
                if (unordered) row.append("/").append(values(result.getObject(col++), false));
                if (ordered) row.append("/").append(values(result.getObject(col), true));
                output.add(row.toString());
            }
            if (generated.isEmpty() || generated.stream().noneMatch(s -> s.contains("groupBy")))
                throw new AssertionError("no executed aggregate code was captured");
            return output.toString();
        }
    }
}
