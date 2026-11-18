package tm;

import java.util.HashMap;
import java.util.List;

/**
 * Countermodels of an exception's message kept from the constructor the engine saw run (the state stream's
 * {@code vwrmzmst}, {@code lib/src/bmc/throwables.rs}). Each method catches an exception that a JDK call the engine
 * runs as one of its models throws, and reads its message. The model makes the exception with another message than
 * the JDK does. {@code main} prints what a JVM says.
 */
public class Thrown {
    /** {@code List.of("a").get(k)} past its one element: the JDK's message is "Index: k Size: 1". */
    public static int listed(int k) {
        try {
            List.of("a").get(k);
            return 0;
        } catch (IndexOutOfBoundsException e) {
            return e.getMessage() == null ? 1 : 2;
        }
    }

    /** The same exception's {@code toString()}: its class's name, then ": " and the message where there is one. */
    public static int listedText(int k) {
        try {
            List.of("a").get(k);
            return 0;
        } catch (IndexOutOfBoundsException e) {
            return e.toString().length();
        }
    }

    /** {@code new HashMap<>(k)} for a negative capacity: the JDK's message is "Illegal initial capacity: k". */
    public static int sized(int k) {
        try {
            new HashMap<String, String>(k);
            return 0;
        } catch (IllegalArgumentException e) {
            return e.getMessage() == null ? 1 : 2;
        }
    }

    /** The message as a caller that records it reads it: {@code getLocalizedMessage()}. */
    public static int sizedLocalized(int k) {
        try {
            new HashMap<String, String>(k);
            return 0;
        } catch (IllegalArgumentException e) {
            String m = e.getLocalizedMessage();
            return m == null ? -1 : m.length();
        }
    }

    public static void main(String[] args) {
        System.out.println("listed=" + listed(2) + " listedText=" + listedText(2) + " sized=" + sized(-1) + " sizedLocalized=" + sizedLocalized(-1));
    }
}
