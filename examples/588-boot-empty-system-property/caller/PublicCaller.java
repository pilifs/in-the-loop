import org.springframework.boot.test.util.TestPropertyValues;

public class PublicCaller {
    private static final String KEY = "example.option";

    static String value() {
        String s = System.getProperty(KEY, "default");
        return s.isEmpty() ? "empty" : s;
    }

    static String run(String initial, boolean nested) {
        String saved = System.getProperty(KEY);
        try {
            if (initial == null) System.clearProperty(KEY);
            else System.setProperty(KEY, initial);
            StringBuilder record = new StringBuilder();
            TestPropertyValues.of(KEY + "=temporary").applyToSystemProperties((Runnable) () -> {
                if (nested) {
                    RuntimeException sentinel = new RuntimeException("inner");
                    try {
                        TestPropertyValues.of(KEY + "=inner").applyToSystemProperties((Runnable) () -> {
                            record.append(value()).append("/");
                            throw sentinel;
                        });
                    } catch (RuntimeException caught) {
                        record.append(caught == sentinel).append("/");
                    }
                }
                record.append(value()).append("/");
            });
            return record.append(value()).toString();
        } finally {
            if (saved == null) System.clearProperty(KEY);
            else System.setProperty(KEY, saved);
        }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> run("", false);
            case "control" -> run(null, false) + ";" + run("original", false);
            case "challenge" -> run("", true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
