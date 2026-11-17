package bc;

import java.util.Locale;

/** An initializer that sets the JVM's default locale to Turkish, then its own static. */
public class Relocaled {
    public static int k;

    static {
        Locale.setDefault(Locale.forLanguageTag("tr"));
        k = 7;
    }
}
