import org.apache.calcite.*;
import org.apache.calcite.jdbc.JavaTypeFactoryImpl;
import org.apache.calcite.rel.type.*;
import org.apache.calcite.rex.*;
import org.apache.calcite.sql.type.SqlTypeName;
import org.apache.calcite.util.TimeString;
import org.apache.calcite.util.TimestampString;

import java.util.*;

public class PublicCaller {
    static String reduce(boolean date, String fractional, boolean character) {
        var types =
                new JavaTypeFactoryImpl(
                        new RelDataTypeSystemImpl() {
                            public int getMaxPrecision(SqlTypeName type) {
                                return type == SqlTypeName.TIME || type == SqlTypeName.TIMESTAMP
                                        ? 9
                                        : super.getMaxPrecision(type);
                            }
                        });
        var b = new RexBuilder(types);
        var exec =
                new RexExecutorImpl(
                        DataContexts.of(
                                Map.of(
                                        DataContext.Variable.TIME_ZONE.camelName,
                                        TimeZone.getTimeZone("GMT"),
                                        DataContext.Variable.LOCALE.camelName,
                                        Locale.US)));
        String text = (date ? "2020-01-01 " : "") + "12:34:56." + fractional;
        RexNode expr =
                b.makeCast(
                        types.createSqlType(
                                date ? SqlTypeName.TIMESTAMP : SqlTypeName.TIME,
                                fractional.length()),
                        b.makeLiteral(text));
        if (character) expr = b.makeCast(types.createSqlType(SqlTypeName.VARCHAR, 30), expr);
        List<RexNode> output = new ArrayList<>();
        exec.reduce(b, List.of(expr), output);
        var literal = (RexLiteral) output.get(0);
        if (character) return literal.getValueAs(String.class);
        return date
                ? literal.getValueAs(TimestampString.class).toString(fractional.length())
                : literal.getValueAs(TimeString.class).toString(fractional.length());
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge"))
            return reduce(true, "123456", true) + "/" + reduce(true, "123457", true);
        String fraction = a[0].equals("control") ? "123" : "123456";
        return reduce(false, fraction, false) + "/" + reduce(true, fraction, false);
    }
}
