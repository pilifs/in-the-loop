import org.apache.commons.configuration2.JSONConfiguration;
import java.io.StringReader;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        JSONConfiguration config = new JSONConfiguration();
        config.read(new StringReader(args[0]));
        return config.getList(String.class, args[1]).toString();
    }
}
