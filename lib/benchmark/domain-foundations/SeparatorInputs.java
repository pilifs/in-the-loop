package foundation;

import com.github.javaparser.utils.LineSeparator;
import organic.TreeOrder;

/** Named caller prestates for the original separator and traversal, on a fresh JVM each time. */
public final class SeparatorInputs {
    public static boolean text(String value) {
        System.setProperty("line.separator", value);
        LineSeparator separator = LineSeparator.SYSTEM;
        StringBuilder escaped = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char unit = value.charAt(i);
            if (unit == '\r') escaped.append("\\r");
            else if (unit == '\n') escaped.append("\\n");
            else escaped.append(unit);
        }
        String expected = escaped.toString();
        String description = new StringBuilder("SYSTEM : (").append(expected).append(")").toString();
        System.setProperty("line.separator", "later");
        return separator.asRawString() == value && separator.asEscapedString().equals(expected)
            && separator.describe().equals(description) && System.getProperty("line.separator") == "later";
    }

    public static boolean absent() {
        System.clearProperty("line.separator");
        try {
            LineSeparator.SYSTEM.asRawString();
            return false;
        } catch (ExceptionInInitializerError failed) {
            if (!(failed.getCause() instanceof NullPointerException)) return false;
            try {
                LineSeparator.SYSTEM.asRawString();
                return false;
            } catch (NoClassDefFoundError erroneous) { return true; }
        }
    }

    private static void set(char first, char second, int length) {
        String value = new String(new char[]{first, second}, 0, length);
        System.setProperty("line.separator", value);
    }

    public static int postorder(int code, char first, char second, int length) {
        set(first, second, length);
        return TreeOrder.postorder(code);
    }
    public static int preorder(int code, char first, char second, int length) {
        set(first, second, length);
        return TreeOrder.preorder(code);
    }
    public static int terminal(int code, char first, char second, int length) {
        set(first, second, length);
        return TreeOrder.terminal(code);
    }

    public static void main(String[] args) {
        boolean ok;
        if (args[0].equals("absent")) ok = absent();
        else if (args[0].equals("text")) {
            String[] samples = {"", "\r", "\n", "\r\n", "x\0", "\uD800\n", "\uDC00\u03A9", "\r\r\n"};
            ok = text(samples[Integer.parseInt(args[1])]);
        } else if (args[0].equals("replay")) {
            int code = Integer.parseInt(args[1]);
            int length = Integer.parseInt(args[4]);
            char first = (char) Integer.parseInt(args[2]), second = (char) Integer.parseInt(args[3]);
            ok = (args.length > 5 && args[5].equals("terminal") ? terminal(code, first, second, length)
                    : postorder(code, first, second, length)) == 0;
        } else {
            int code = Integer.parseInt(args[1]);
            ok = switch (args[0]) {
                case "terminal" -> terminal(code, '\r', '\n', 2);
                case "preorder" -> preorder(code, '\r', '\n', 2);
                default -> postorder(code, '\r', '\n', 2);
            } == Integer.parseInt(args[2]);
        }
        if (!ok) throw new AssertionError(args[0]);
    }
}
