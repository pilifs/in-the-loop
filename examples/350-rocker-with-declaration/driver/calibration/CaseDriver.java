package calibration;

import com.fizzed.rocker.model.WithStatement;
import com.fizzed.rocker.runtime.ParserException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class CaseDriver {
    private static String direct(int code) throws Exception {
        String input = code == 0 ? "(String s = \"test\",)" : "(String s = \"test\")";
        try {
            WithStatement w = WithStatement.parse(input, "template-path");
            WithStatement.VariableWithExpression variable = w.getVariables().get(0);
            return variable.getVariable().getType() + " " + variable.getVariable().getName() + "=" + variable.getValueExpression();
        } catch (ParserException e) {
            return e.getMessage();
        }
    }

    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 2; code++) {
            String actual = encoded(direct(code));
            String projected = encoded(Projection.diagnostic(code != 0));
            System.out.println("{\"code\":" + code + ",\"direct\":\"" + actual
                    + "\",\"adapter\":\"" + projected + "\"}");
        }
    }
}
