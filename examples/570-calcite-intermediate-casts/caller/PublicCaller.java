import org.apache.calcite.test.CalciteAssert;

import java.sql.*;
import java.util.*;

public class PublicCaller {
    static String columns(Connection c, String expr) throws Exception {
        try (var s = c.createStatement();
                var r = s.executeQuery("SELECT " + expr + " FROM emp WHERE empno=7369")) {
            if (!r.next()) throw new AssertionError("SCOTT.EMP row missing");
            List<String> v = new ArrayList<>();
            for (int i = 1; i <= r.getMetaData().getColumnCount(); i++) v.add(r.getString(i));
            if (r.next()) throw new AssertionError("duplicate employee");
            return String.join("/", v);
        }
    }

    public static String observe(String[] a) throws Exception {
        try (var c = CalciteAssert.that().with(CalciteAssert.SchemaSpec.SCOTT).connect()) {
            if (a[0].equals("control"))
                return columns(
                        c, "CAST(deptno AS VARCHAR),CAST(CAST(deptno AS INTEGER) AS VARCHAR)");
            if (a[0].equals("intent"))
                return columns(
                        c,
                        "CAST(CAST(deptno AS DOUBLE) AS VARCHAR),CAST(CAST(deptno AS DECIMAL(5,2))"
                            + " AS VARCHAR),CAST(CAST(sal AS DECIMAL(10,4)) AS"
                            + " VARCHAR),CAST(CAST(deptno AS INTEGER) AS VARCHAR)");
            String shortText = "CAST(CAST(deptno AS DOUBLE)/3e0 AS VARCHAR(3))";
            String first = columns(c, shortText),
                    nested = columns(c, "CAST(" + shortText + " AS DOUBLE)");
            try (var st = c.prepareStatement("VALUES CAST(CAST(? AS VARCHAR(3)) AS DOUBLE)")) {
                st.setString(1, first);
                try (var r = st.executeQuery()) {
                    r.next();
                    return first + "/" + nested + "/" + r.getDouble(1);
                }
            }
        }
    }
}
