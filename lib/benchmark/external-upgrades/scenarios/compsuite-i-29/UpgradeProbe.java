import com.uber.profiling.Arguments;
import com.uber.profiling.ConfigProvider;
import java.util.*;

public final class UpgradeProbe {
    public static final class Settings implements ConfigProvider {
        public Map<String, Map<String, List<String>>> getConfig() {
            Map<String, Map<String, List<String>>> all = new HashMap<>();
            Map<String, List<String>> root = new HashMap<>(), tagged = new HashMap<>();
            root.put("metricInterval", Arrays.asList("9000"));
            root.put("ioProfiling", Arrays.asList("true"));
            tagged.put("metricInterval", Arrays.asList("9001"));
            tagged.put("ioProfiling", Arrays.asList("false"));
            all.put("", root);
            all.put("tag1", tagged);
            return all;
        }
    }
    public static String observe(String[] input) {
        Arguments options = Arguments.parseArgs("tag=" + input[0] + ",metricInterval=1000,ioProfiling=false,configProvider=" + Settings.class.getName());
        options.runConfigProvider();
        return options.getTag() + "/" + options.getMetricInterval() + "/" + options.isIoProfiling();
    }
}
