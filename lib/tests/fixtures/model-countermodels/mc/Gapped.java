package mc;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;

/**
 * Collections of the JDK classes the own checker runs a model of on request ({@code --model}), each made by a call
 * the model does not keep: under {@code --gaps assume} the checker takes such a call to return a new object, or to
 * construct one and do nothing else, and then runs the model's methods on that object's fields, which nothing wrote.
 * {@code main} prints what a JVM says of each.
 */
public class Gapped {
    /** A deque of one element, cloned: {@code ArrayDeque.clone()} is the JDK's, and the copy has that element. */
    public static int cloned() {
        ArrayDeque<String> deque = new ArrayDeque<>();
        deque.push("x");
        return deque.clone().size();
    }

    /** A deque made from a list of one element by {@code ArrayDeque(Collection)}, which the model does not keep. */
    public static int copied() {
        return new ArrayDeque<String>(Arrays.asList("x")).size();
    }

    /** The same of {@code ArrayList(Collection)}, which the ArrayList model does not keep. */
    public static int listed() {
        return new ArrayList<String>(Arrays.asList("x")).size();
    }

    public static void main(String[] args) {
        System.out.println("cloned=" + cloned() + " copied=" + copied() + " listed=" + listed());
    }
}
