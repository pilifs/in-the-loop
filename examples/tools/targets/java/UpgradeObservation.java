import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Base64;

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
        try {
            String returned = (String) observe.invoke(null, (Object) inputs);
            System.out.println("UPGRADE-OBSERVATION return " + encode(returned));
        } catch (InvocationTargetException exception) {
            Throwable thrown = exception.getCause();
            System.out.println("UPGRADE-OBSERVATION throw " + thrown.getClass().getName());
            StringBuilder detail = new StringBuilder();
            Throwable cause = thrown;
            for (int depth=0; cause!=null && depth<4; depth++, cause=cause.getCause()) {
                if (depth>0) detail.append(" caused by ");
                detail.append(cause.getClass().getName()).append(": ").append(cause.getMessage());
                if (cause.getStackTrace().length != 0)
                    detail.append(" at ").append(cause.getStackTrace()[0]);
            }
            System.out.println("UPGRADE-DETAIL " + encode(detail.toString()));
            for (StackTraceElement frame : thrown.getStackTrace()) {
                System.out.println("UPGRADE-FRAME " + frame.getClassName() + "#" + frame.getMethodName());
            }
        }
    }
}
