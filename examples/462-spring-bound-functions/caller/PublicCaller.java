import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import org.springframework.expression.Expression;
import org.springframework.expression.spel.SpelEvaluationException;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;

public class PublicCaller {
    static String evaluate(Expression expression, StandardEvaluationContext context) {
        try {
            Object value = expression.getValue(context);
            return value.getClass().getSimpleName() + "=" + value;
        } catch (SpelEvaluationException e) {
            return e.getClass().getSimpleName();
        }
    }

    public static String observe(String[] args) throws Exception {
        var parser = new SpelExpressionParser();
        var context = new StandardEvaluationContext();
        if (args[0].equals("static")) {
            context.registerFunction("num", Integer.class.getMethod("toString", int.class));
            return evaluate(parser.parseExpression("#num(7)"), context);
        }
        var concat = MethodHandles.publicLookup().findVirtual(String.class, "concat",
                MethodType.methodType(String.class, String.class));
        context.setVariable("tag", concat.bindTo("red-"));
        var expression = parser.parseExpression("#tag('fox')");
        String first = evaluate(expression, context);
        if (args[0].equals("red")) return first;
        try {
            context.registerFunction("tag", concat.bindTo("blue-"));
        } catch (NoSuchMethodError absent) {
            return first + " registerFunction=absent";
        }
        return first + " " + evaluate(expression, context);
    }
}
