package claims;

import java.util.Random;
import java.util.StringJoiner;

/**
 * A {@code StringJoiner}, as Spring's {@code DefaultMessageCodesResolver.Format.toDelimitedString} joins a binding
 * error's message code (example 286): each method returns whether the joiner does what the JDK documents, written out
 * over {@code charAt}, so a proof of it with {@code --model java.util.StringJoiner} is a proof that the model and the
 * definition agree on every input of the bound, and {@code main} runs the same methods on a JVM over sampled inputs,
 * on the JDK's joiner.
 */
public class Joiners {
    /**
     * The non-null elements of {@code a} added in order: each {@code add} returns the joiner, and {@code toString()} is
     * a new String (no element, not the delimiter), the elements with the delimiter between each two; a null
     * delimiter is a {@code NullPointerException} with the JDK's message. Only joins of at least one unit: an empty
     * one is {@code new String()}, the JDK call the model names.
     */
    public static boolean joined(String[] a, String d) {
        StringJoiner joiner;
        try {
            joiner = new StringJoiner(d);
        } catch (NullPointerException e) {
            return d == null && "The delimiter must not be null".equals(e.getMessage());
        }
        if (d == null) {
            return false;
        }
        int length = 0;
        int count = 0;
        for (int i = 0; i < a.length; i++) {
            if (a[i] == null) {
                continue;
            }
            if (joiner.add(a[i]) != joiner) {
                return false;
            }
            length += (count > 0 ? d.length() : 0) + a[i].length();
            count++;
        }
        if (length == 0) {
            return true;
        }
        String r = joiner.toString();
        if (r.length() != length || r == d) {
            return false;
        }
        int at = 0;
        boolean first = true;
        for (int i = 0; i < a.length; i++) {
            if (a[i] == null) {
                continue;
            }
            if (r == a[i]) {
                return false;
            }
            if (!first) {
                for (int k = 0; k < d.length(); k++) {
                    if (r.charAt(at++) != d.charAt(k)) {
                        return false;
                    }
                }
            }
            first = false;
            for (int k = 0; k < a[i].length(); k++) {
                if (r.charAt(at++) != a[i].charAt(k)) {
                    return false;
                }
            }
        }
        return true;
    }

    /** A null element is added as the four units {@code null}. */
    public static boolean addedNull(String d) {
        if (d == null) {
            return true;
        }
        String r = new StringJoiner(d).add(null).add("a").toString();
        return r.length() == 5 + d.length() && r.startsWith("null") && r.charAt(4 + d.length()) == 'a';
    }

    /** An empty join, which the model leaves to the JDK's {@code new String()}. */
    public static boolean empty(String d) {
        return new StringJoiner(d).toString().length() == 0;
    }

    /** Runs each method over sampled Strings (of "", "a", "b", ".", "ab", null) on this JVM; prints "ok" or the first that fails. */
    public static void main(String[] args) {
        String[] texts = {"", "a", "b", ".", "ab", null};
        int samples = Integer.parseInt(args[0]);
        Random random = new Random(286);
        for (int s = 0; s < samples; s++) {
            String[] a = new String[random.nextInt(4)];
            for (int i = 0; i < a.length; i++) {
                a[i] = texts[random.nextInt(texts.length)];
            }
            String d = texts[random.nextInt(texts.length)];
            if (!joined(a, d) || !addedNull(d) || d != null && !empty(d)) {
                System.out.println("fails: " + java.util.Arrays.toString(a) + " d " + d);
                return;
            }
        }
        System.out.println("ok");
    }
}
