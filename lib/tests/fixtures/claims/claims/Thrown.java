package claims;

import java.util.UnknownFormatConversionException;

/**
 * An exception's message and cause, as a library that records an error reads them back (example 286: Spring's binder
 * keeps {@code ex.getLocalizedMessage()} as a binding error's default message, and its
 * {@code NestedRuntimeException.getMessage} appends the cause's {@code toString()}). The first methods return
 * whether the JDK's answers are the ones {@code Throwable}'s Javadoc gives, true on a JVM; the rest are what the
 * engine must not prove, each false on a JVM. {@code main} prints what a JVM answers.
 */
public class Thrown {
    /** As Spring's {@code NestedRuntimeException}: its message appends the cause's {@code toString()}. */
    static class Nested extends RuntimeException {
        Nested(String message, Throwable cause) {
            super(message, cause);
        }

        @Override
        public String getMessage() {
            String own = super.getMessage();
            Throwable cause = getCause();
            if (cause == null) {
                return own;
            }
            StringBuilder sb = new StringBuilder(64);
            if (own != null) {
                sb.append(own).append("; ");
            }
            sb.append("nested exception is ").append(cause);
            return sb.toString();
        }
    }

    /** Counts the stack traces filled in: the JVM calls this inside {@code Throwable}'s constructor. */
    static int filled;

    static class Counting extends RuntimeException {
        Counting(String message) {
            super(message);
        }

        @Override
        public synchronized Throwable fillInStackTrace() {
            filled++;
            return this;
        }
    }

    /** An exception whose {@code toString()} is its own. */
    static class Shown extends IllegalStateException {
        Shown(String message) {
            super(message);
        }

        @Override
        public String toString() {
            return "shown";
        }
    }

    /** What each constructor sets: the message (null for none) and the cause (null for none), and the class. */
    public static boolean kept(String m) {
        IllegalStateException plain = new IllegalStateException();
        IllegalStateException said = new IllegalStateException(m);
        IllegalArgumentException caused = new IllegalArgumentException(m, said);
        IllegalStateException unsaid = new IllegalStateException((String) null);
        return plain.getMessage() == null && plain.getCause() == null && said.getMessage() == m && said.getLocalizedMessage() == m
                && said.getCause() == null && caused.getMessage() == m && caused.getCause() == said && unsaid.getMessage() == null
                && plain.getClass() == IllegalStateException.class && caused.getClass().getName().equals("java.lang.IllegalArgumentException");
    }

    /** {@code toString()}: the class's name, then {@code ": "} and the message where there is one. */
    public static boolean shown(String m) {
        return new IllegalStateException().toString().equals("java.lang.IllegalStateException")
                && new IllegalArgumentException(m).toString().equals("java.lang.IllegalArgumentException: " + m);
    }

    /** An application's {@code getMessage()} runs where {@code getLocalizedMessage()} calls it, as Spring's does. */
    public static boolean nested(String m) {
        Nested n = new Nested("outer", new IllegalStateException(m));
        return n.getLocalizedMessage().equals("outer; nested exception is java.lang.IllegalStateException: " + m)
                && new Nested(m, null).getLocalizedMessage() == m;
    }

    /** {@code StringBuilder(int)} is empty; {@code append(Object)} of a String is its units, and of null {@code null}. */
    public static boolean appended(String s) {
        Object o = s;
        StringBuilder sb = new StringBuilder(16);
        sb.append(o).append((Object) null);
        return sb.toString().equals(s + "null") && new StringBuilder(0).length() == 0;
    }

    /** False on a JVM, which counts one stack trace filled in. */
    public static boolean countsNothing() {
        filled = 0;
        new Counting("m");
        return filled == 0;
    }

    /** False on a JVM: this JDK exception's constructor throws {@code NullPointerException} for null. */
    public static boolean nullConversion() {
        try {
            new UnknownFormatConversionException(null);
            return true;
        } catch (NullPointerException e) {
            return false;
        }
    }

    /** False on a JVM: the exception's own {@code toString()} is appended. */
    public static boolean shownAppended() {
        return new StringBuilder().append(new Shown("m")).toString().equals("claims.Thrown$Shown: m");
    }

    /** False on a JVM: {@code toString()} uses the overridden message. */
    public static boolean nestedShown() {
        return new Nested("outer", new IllegalStateException("m")).toString().equals("claims.Thrown$Nested: outer");
    }

    public static void main(String[] args) {
        System.out.println("kept=" + kept("m") + " " + kept("") + " shown=" + shown("m") + " " + shown("") + " nested=" + nested("m") + " appended=" + appended("ab")
                + " countsNothing=" + countsNothing() + " nullConversion=" + nullConversion() + " shownAppended=" + shownAppended() + " nestedShown=" + nestedShown());
    }
}
