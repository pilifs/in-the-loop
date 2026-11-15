package claims;

import java.util.Arrays;
import java.util.regex.Pattern;

/** A wildcard matcher that calls itself on every '*', as a library's would, and what is said of it. */
public final class Glob {
    private Glob() {}

    static int calls;

    /** Whether the pattern ('*' any sequence, anything else itself) matches all of the text. */
    public static boolean matches(String pattern, String text) {
        if (pattern.isEmpty()) {
            return text.isEmpty();
        }
        if (pattern.charAt(0) == '*') {
            for (int skipped = 0; skipped <= text.length(); skipped++) {
                if (matches(pattern.substring(1), text.substring(skipped))) {
                    return true;
                }
            }
            return false;
        }
        return !text.isEmpty() && pattern.charAt(0) == text.charAt(0) && matches(pattern.substring(1), text.substring(1));
    }

    /** The same answer, and a count of the calls in a static field: nothing a summary of the result could state. */
    public static boolean counted(String pattern, String text) {
        calls++;
        return matches(pattern, text);
    }

    /** The same answer where the two are not one object: its result depends on which objects it is given. */
    public static boolean unlessSame(String pattern, String text) {
        return pattern != text && matches(pattern, text);
    }

    /** Whether some pattern matches the field: what a check of a deny list asks, pattern by pattern. */
    public static boolean any(String[] patterns, String field) {
        for (String pattern : patterns) {
            if (pattern != null && matches(pattern, field)) {
                return true;
            }
        }
        return false;
    }

    /** The statement of the same, in the library's words. */
    public static boolean anyByRegex(String[] patterns, String field) {
        return Arrays.stream(patterns).anyMatch(p -> p != null && Pattern.compile(String.join(".*", Arrays.stream(p.split("\\*", -1)).map(Pattern::quote).toArray(String[]::new)), Pattern.DOTALL).matcher(field).matches());
    }
}
