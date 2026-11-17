package wd;

import java.util.Date;
import java.util.HashSet;

/**
 * Objects made by a JDK call whose declared return type is wider than the object's class ({@code Object clone()}).
 * Under {@code --gaps assume} the checker takes such a call to return "a new object, never null", and makes it an
 * object of exactly the declared class, so a type test on it says what the JDK's object is not. {@code main} prints
 * what a JVM says of each.
 */
public class Widened {
    /** HashSet.clone() is declared to return Object; the object is a HashSet of one element. */
    public static int setCloned() {
        HashSet<String> set = new HashSet<>();
        set.add("x");
        Object copy = set.clone();
        return copy instanceof HashSet ? 1 : 0;
    }

    /** The same copy, cast and asked its size: -1 only where the cast fails. */
    public static int setClonedSize() {
        HashSet<String> set = new HashSet<>();
        set.add("x");
        try {
            return ((HashSet<?>) set.clone()).size();
        } catch (ClassCastException e) {
            return -1;
        }
    }

    /** No model of the class: Date.clone() is declared to return Object, and the object is a Date. */
    public static int dateCloned() {
        Object copy = new Date(0L).clone();
        return copy instanceof Date ? 1 : 0;
    }

    public static void main(String[] args) {
        System.out.println("setCloned=" + setCloned() + " setClonedSize=" + setClonedSize() + " dateCloned=" + dateCloned());
    }
}
