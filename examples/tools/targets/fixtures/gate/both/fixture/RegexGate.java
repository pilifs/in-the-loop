package fixture;

import java.util.regex.Pattern;

/** The same in both revisions: a check through java.util.regex in a form the tool's own checker does not implement
 * (a possessive quantifier), so a strict proof that reaches it is refused by name: the deliberate capability refusal. */
public final class RegexGate {
    private static final Pattern NAME = Pattern.compile("[a-z]++");

    private RegexGate() {
    }

    public static boolean allowed(String field) {
        return field != null && NAME.matcher(field).matches();
    }
}
