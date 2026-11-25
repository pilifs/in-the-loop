import java.util.ArrayList;
import java.util.List;
import net.sf.jsqlparser.expression.LongValue;
import net.sf.jsqlparser.parser.AbstractJSqlParser.Dialect;
import net.sf.jsqlparser.parser.CCJSqlParserUtil;
import net.sf.jsqlparser.schema.Table;
import net.sf.jsqlparser.statement.alter.*;
import net.sf.jsqlparser.statement.alter.AlterExpression.ColumnDataType;
import net.sf.jsqlparser.statement.alter.AlterExpression.ColumnSetDefault;
import net.sf.jsqlparser.statement.create.table.ColDataType;
import net.sf.jsqlparser.util.deparser.*;

public class PublicCaller {
    static Alter parse(String sql) throws Exception {
        return (Alter) CCJSqlParserUtil.parse(sql, p -> p.withDialect(Dialect.POSTGRESQL));
    }
    static Alter mixed(boolean type, int stale) throws Exception {
        var action = new AlterExpressionDrop();
        action.setOperation(AlterOperation.ALTER);
        action.hasColumn(true);
        var column = new ColumnDataType(type).withColumnName("id");
        if (type) {
            column.withColDataType(new ColDataType("INT"));
            column.setUsingExpression(CCJSqlParserUtil.parseExpression("id + 2"));
            action.addParameters("CASCADE");
        } else column.setIdentityAlterations(List.of(new IdentityAlteration(IdentityAlteration.Kind.RESTART)));
        action.addColDataType(column);
        action.addColSetDefault(ColumnSetDefault.fromExpression("other", new LongValue(stale)));
        var alter = new Alter();
        alter.setTable(new Table("t"));
        alter.addAlterExpression(action);
        return alter;
    }
    static String render(Alter action, boolean reparse) throws Exception {
        var sql = new StringBuilder();
        var visited = new ArrayList<Long>();
        var expression = new ExpressionDeParser() {
            public <S> StringBuilder visit(LongValue v, S context) {
                visited.add(v.getValue());
                return getBuilder().append(v.getValue()+100);
            }
        };
        var stock = new StringBuilder();
        action.accept(new StatementDeParser(stock), null);
        action.accept(new StatementDeParser(expression, new SelectDeParser(), sql), null);
        String parsed = "";
        if (reparse) {
            try { parsed = " parsed=" + parse(sql.toString()); }
            catch (net.sf.jsqlparser.JSQLParserException ex) { parsed = " parsed=throws " + ex.getClass().getName(); }
        }
        return "toString="+action+" stock="+stock+" custom="+sql+" visits="+visited+parsed;
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("type")) return render(mixed(true,1),true) + " | " + render(mixed(true,9),true);
        return render(args[0].equals("default") ? parse("ALTER TABLE t ALTER COLUMN amount SET DEFAULT (1 + 2)")
                : mixed(false,1), false);
    }
}
