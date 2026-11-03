package fixtures;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/**
 * Code that reaches JDK classes the tool ships models of (lib/models): a static initializer that reads a standard
 * charset, a digit lookup in the JDK's Unicode table, a charset lookup by name, and autoboxing. The proofs over it
 * need the models on JBMC's class path, and the interpreter runs the same models.
 */
public final class Models {

    /** The name of the encoding, read from a modelled static field in this class's static initializer. */
    public static final String ENCODING = StandardCharsets.UTF_8.name();

    private Models() {
    }

    /** The value of a hexadecimal digit by the JDK's table (a Unicode digit counts), or -1. */
    public static int hexDigit(char ch) {
        return Character.digit(ch, 16);
    }

    /** Whether a name picked by its first letter is a standard charset, by the model's lookup. */
    public static boolean standard(char first) {
        String name = first == 'u' ? "utf-8" : first == 'a' ? "ascii" : "x-" + first;
        return Charset.isSupported(name) && Charset.forName(name).name().length() > 0;
    }

    /** The canonical name of a charset that may not exist: an UnsupportedCharsetException for most letters. */
    public static String canonical(char first) {
        return Charset.forName(first == 'u' ? "UTF8" : "x-" + first).name();
    }

    /** Boxes and unboxes: the JDK's valueOf reads the cache the tool models. */
    public static int boxed(int n) {
        Integer i = Integer.valueOf(n);
        return i.intValue();
    }
}
