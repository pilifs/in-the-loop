import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Properties;

/** The process property is an input. The public caller and the registered predicate are untouched. */
public final class ConfigurationPrestate {
    private static void binding(String owner) throws Exception {
        Class<?> cls = Class.forName(owner, false, ConfigurationPrestate.class.getClassLoader());
        try (var source = cls.getResourceAsStream("/" + owner.replace('.', '/') + ".class")) {
            System.out.println(owner + "\t" + HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(source.readAllBytes())));
        }
    }

    private static void reportFailure(Throwable t) {
        for (Throwable cause = t; cause != null; cause = cause.getCause()) {
            System.out.println("cause\t" + cause.getClass().getName());
            for (StackTraceElement frame : cause.getStackTrace()) {
                if (frame.getClassName().contains("ConfigurationInterpolator$DefaultPrefixLookupsHolder")) {
                    System.out.println("frame\t" + frame.getClassName() + "." + frame.getMethodName());
                }
            }
        }
    }

    public static void main(String[] args) throws Exception {
        String setting = args[0], key = args[1], op = args[2], holderName = args[3];
        binding("UpgradeProbe");
        binding("UpgradeCallerClaim");
        binding(holderName);
        Properties parent = System.getProperties();
        if (parent.containsKey(key) || parent.getProperty(key) != null) throw new AssertionError("unexpected startup property");
        switch (setting) {
            case "default" -> { }
            case "own-invalid" -> System.setProperty(key, "_");
            case "inherited-invalid" -> {
                System.setProperty(key, "_");
                System.setProperties(new Properties(parent));
            }
            default -> throw new IllegalArgumentException(setting);
        }
        Properties table = System.getProperties();
        System.out.println("own\t" + table.containsKey(key));
        System.out.println("lookup\t" + table.getProperty(key));
        switch (op) {
            case "predicate" -> System.out.println("matched\t" + UpgradeCallerClaim.matches(Integer.parseInt(args[4])));
            case "observe" -> {
                String[] input = Arrays.copyOfRange(args, 4, args.length);
                for (int attempt = 1; attempt <= 2; attempt++) {
                    System.out.println("call\t" + attempt);
                    try {
                        String value = UpgradeProbe.observe(input);
                        System.out.println(value == null ? "null\t" : "value\t" + value);
                    } catch (Throwable failure) {
                        reportFailure(failure);
                    }
                }
            }
            default -> throw new IllegalArgumentException(op);
        }
    }
}
