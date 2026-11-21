import org.apache.commons.validator.util.ValidatorUtils;

public final class UpgradeProbe {
    public static final class Bean {
        private final String title;
        public Bean(String title) { this.title = title; }
        public String getTitle() { return title; }
        public int getQuantity() { return 7; }
    }
    public static String observe(String[] args) {
        return ValidatorUtils.getValueAsString(new Bean(args[0]), args[1]);
    }
}
