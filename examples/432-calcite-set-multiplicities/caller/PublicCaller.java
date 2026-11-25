import java.sql.*;
import java.util.ArrayList;
import java.util.function.Consumer;
import org.apache.calcite.plan.RelOptPlanner;
import org.apache.calcite.rel.rules.CoreRules;
import org.apache.calcite.runtime.Hook;

public class PublicCaller {
    static String rows(Statement st, String left, String op, String right) throws SQLException {
        String select = "SELECT x+1 AS x, y FROM (VALUES ";
        String sql = "SELECT y FROM (" + select + left + ") AS a(x,y) " + op
                + " " + select + right + ") AS b(x,y))";
        var values = new ArrayList<Integer>();
        try (var rs = st.executeQuery(sql)) { while (rs.next()) values.add(rs.getInt(1)); }
        return values.toString();
    }
    static String both(Statement st, String left, String right) throws SQLException {
        return rows(st, left, "EXCEPT ALL", right) + "/" + rows(st, left, "INTERSECT ALL", right);
    }
    public static String observe(String[] args) throws Exception {
        int[] configured = {0};
        try (var hook = Hook.PLANNER.addThread((Consumer<RelOptPlanner>) planner -> {
                planner.addRule(CoreRules.PROJECT_SET_OP_TRANSPOSE);
                if (planner.getRules().contains(CoreRules.PROJECT_SET_OP_TRANSPOSE)) configured[0]++;
            }); var connection = DriverManager.getConnection("jdbc:calcite:");
             var st = connection.createStatement()) {
            String result;
            if (args[0].equals("duplicates")) {
                String left = "(1,10),(1,10),(2,10)";
                result = both(st, left, "(1,10),(3,10),(3,10)") + " | " + both(st, left, left);
            } else if (args[0].equals("union")) result = rows(st, "(1,10)", "UNION ALL", "(2,10)");
            else result = both(st, "(1,10)", "(2,10)");
            return "rule=" + (configured[0] > 0) + " rows=" + result;
        }
    }
}
