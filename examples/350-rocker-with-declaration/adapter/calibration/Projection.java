package calibration;

import com.fizzed.rocker.model.WithStatement;
import com.fizzed.rocker.runtime.ParserException;

public final class Projection {
    public static String diagnostic(boolean valid) throws Exception {
        String input = valid ? "(String s = \"test\")" : "(String s = \"test\",)";
        try {
            WithStatement.VariableWithExpression v = WithStatement.parse(input, "template-path").getVariables().get(0);
            return v.getVariable().getType() + " " + v.getVariable().getName() + "=" + v.getValueExpression();
        } catch (ParserException error) {
            return error.getMessage();
        }
    }
}
