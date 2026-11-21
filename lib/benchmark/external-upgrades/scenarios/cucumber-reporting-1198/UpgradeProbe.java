import com.fasterxml.jackson.databind.ObjectMapper;
import net.masterthought.cucumber.json.support.Argument;
import net.masterthought.cucumber.util.StepNameFormatter;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        Argument[] values = new ObjectMapper().readValue(args[1], Argument[].class);
        return StepNameFormatter.format(args[0], values, "<b>", "</b>");
    }
}
