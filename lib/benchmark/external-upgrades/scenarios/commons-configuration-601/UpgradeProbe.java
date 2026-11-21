import org.apache.commons.configuration2.YAMLConfiguration;
import java.io.StringReader;

public final class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        YAMLConfiguration config = new YAMLConfiguration();
        config.read(new StringReader(args[0]));
        java.util.List<String> values = config.getList(String.class, args[1]);
        return values == null ? null : values.toString();
    }
}
