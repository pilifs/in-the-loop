import com.fizzed.rocker.model.WithStatement;
import com.fizzed.rocker.runtime.ParserException;

public final class Observe {
    public static void main(String[] args) throws Exception {
        for (String text : new String[]{"(String s = \"test\",)", "(String s = \"test\")"}) {
            try {
                WithStatement result = WithStatement.parse(text, "template-path");
                WithStatement.VariableWithExpression variable = result.getVariables().get(0);
                System.out.println("return\t" + result.getVariables().size() + "\t"
                        + variable.getVariable().getType() + "\t" + variable.getVariable().getName()
                        + "\t" + variable.getValueExpression());
            } catch (ParserException error) {
                System.out.println("reject\t" + error.getClass().getName() + "\t" + error.getLineNumber()
                        + "\t" + error.getColumnNumber() + "\t" + error.getMessage());
            }
        }
    }
}
