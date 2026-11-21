import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Set;

/** Invoke one supplied caller scenario in a fresh JVM and preserve every UTF-16 code unit. */
public final class UpgradeObservation {
    private static String encode(String text) {
        if (text == null) return "-";
        byte[] bytes = new byte[2 * text.length()];
        for (int i = 0; i < text.length(); ++i) {
            char ch = text.charAt(i);
            bytes[2*i] = (byte)(ch >>> 8);
            bytes[2*i+1] = (byte)ch;
        }
        return Base64.getEncoder().encodeToString(bytes);
    }

    private static String decode(String encoded) {
        if (encoded.equals("-")) return null;
        byte[] bytes = Base64.getDecoder().decode(encoded);
        if (bytes.length % 2 != 0) throw new IllegalArgumentException("odd UTF-16 byte count");
        char[] units = new char[bytes.length / 2];
        for (int i = 0; i < units.length; i++)
            units[i] = (char)(((bytes[2*i] & 255) << 8) | (bytes[2*i+1] & 255));
        return new String(units);
    }

    public static void main(String[] args) throws Exception {
        Method observe = Class.forName(args[0]).getMethod("observe", String[].class);
        String[] inputs = Arrays.copyOfRange(args, 1, args.length);
        for (int i = 0; i < inputs.length; i++) inputs[i] = decode(inputs[i]);
        try (BufferedWriter output = Files.newBufferedWriter(Paths.get(System.getProperty("upgrade.observation.file")),
                StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            observe(output, observe, inputs);
        }
    }

    private static void observe(BufferedWriter output, Method observe, String[] inputs) throws Exception {
        try {
            String returned = (String) observe.invoke(null, (Object) inputs);
            output.write("UPGRADE-OBSERVATION return " + encode(returned) + "\n");
        } catch (InvocationTargetException exception) {
            writeFailure(output, exception.getCause());
        }
    }

    private static String rootMessage(Throwable cause) {
        return encode(cause.getMessage());
    }

    // The debugger binds this argument to the very object observed at a JVM exception event.
    private static void writeFailure(BufferedWriter output, Throwable thrown) throws Exception {
        output.write("UPGRADE-OBSERVATION throw " + thrown.getClass().getName() + "\n");
        StringBuilder detail = new StringBuilder();
        Set<Throwable> seen = Collections.newSetFromMap(new IdentityHashMap<Throwable, Boolean>());
        Throwable last = thrown;
        for (Throwable cause = thrown; cause != null && seen.size() < 16 && seen.add(cause); cause = cause.getCause()) {
            last = cause;
            if (detail.length() > 0) detail.append(" caused by ");
            detail.append(cause.getClass().getName()).append(": ").append(cause.getMessage());
            if (cause.getStackTrace().length != 0) detail.append(" at ").append(cause.getStackTrace()[0]);
            output.write("UPGRADE-CAUSE " + cause.getClass().getName() + "\n");
        }
        output.write("UPGRADE-LAST-CAUSE " + rootMessage(last) + "\n");
        output.write("UPGRADE-DETAIL " + encode(detail.toString()) + "\n");
    }
}
