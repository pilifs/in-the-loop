package java.util;

/**
 * The model of {@code java.util.StringJoiner}: the delimiter and the elements added so far, joined by
 * {@code toString()} as the JDK's does it. The own checker runs it only for a check that asks for it
 * ({@code --model java.util.StringJoiner}); otherwise the class is the JDK's, whose calls the checker does not run.
 * Spring's {@code DefaultMessageCodesResolver.Format.toDelimitedString} joins each message code of a binding error
 * with one (example 286).
 *
 * <p>Kept, each as the JDK's does it (JDK 17 to 25): {@code StringJoiner(CharSequence)}, with its
 * {@code NullPointerException("The delimiter must not be null")}, the delimiter's {@code toString()} kept;
 * {@code add(CharSequence)}, the element's {@code String.valueOf} ({@code "null"} for null) appended and the joiner
 * returned; and {@code toString()}, the elements with the delimiter between each two, a new String. It is built by
 * the {@code StringBuilder} the checker models, whose {@code toString()} is the literal {@code ""} when empty where
 * the JDK's join makes a new empty String, so an empty result is {@code new String()}, the JDK's constructor and a
 * JDK call the checker does not run. A result longer than the checker's builder holds ends the run with no verdict,
 * where a JVM would throw {@code OutOfMemoryError} only past {@code Integer.MAX_VALUE} units.
 *
 * <p>Left out, each the JDK call it names: the constructor with a prefix and a suffix, {@code setEmptyValue},
 * {@code merge} and {@code length}.
 */
public final class StringJoiner {
    // Not private: a private field would be read through a method javac adds.
    String delimiter;
    String[] elements;

    public StringJoiner(CharSequence delimiter) {
        if (delimiter == null) {
            throw new NullPointerException("The delimiter must not be null");
        }
        this.delimiter = delimiter.toString();
        elements = new String[0];
    }

    public StringJoiner add(CharSequence newElement) {
        // String.valueOf(Object), written out.
        String element = newElement == null ? "null" : newElement.toString();
        elements = Arrays.copyOf(elements, elements.length + 1);
        elements[elements.length - 1] = element;
        return this;
    }

    public String toString() {
        StringBuilder joined = new StringBuilder();
        for (int i = 0; i < elements.length; i++) {
            if (i > 0) {
                joined.append(delimiter);
            }
            joined.append(elements[i]);
        }
        if (joined.length() == 0) {
            return new String();
        }
        return joined.toString();
    }
}
