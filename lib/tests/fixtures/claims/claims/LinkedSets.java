package claims;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Random;
import java.util.Set;

/**
 * A {@code LinkedHashSet} of names, as Spring's {@code DefaultMessageCodesResolver} collects a binding error's message
 * codes and hands them on with {@code StringUtils.toStringArray} (example 286): each method returns whether the set
 * does what the JDK documents, written out over {@code equals}, so a proof of it with
 * {@code --model java.util.LinkedHashSet} is a proof that the model and the definition agree on every input of the
 * bound, and {@code main} runs the same methods on a JVM over sampled inputs, on the JDK's set.
 */
public class LinkedSets {
    /**
     * Added in order: each {@code add} true exactly when no earlier name equals it, the size the number of distinct
     * names, each name contained, and {@code toArray()}, {@code toArray(new String[0])} and
     * {@code toArray} of an array of {@code n} names each the distinct names in the order first added, the last two
     * {@code String[]}s (String is final, so an instance of {@code String[]} is of exactly that class), the given
     * array returned when it is long enough, with a null after the names when it is longer
     * (the names it held are "z", so the null is the set's).
     */
    public static boolean ordered(String[] a, int n) {
        if (n < 0 || n > 4) {
            return true;
        }
        Set<String> set = new LinkedHashSet<>();
        if (!set.isEmpty() || set.size() != 0) {
            return false;
        }
        String[] distinct = new String[a.length];
        int count = 0;
        for (int i = 0; i < a.length; i++) {
            boolean seen = false;
            for (int j = 0; j < count; j++) {
                seen |= distinct[j] == null ? a[i] == null : distinct[j].equals(a[i]);
            }
            if (set.add(a[i]) == seen) {
                return false;
            }
            if (!seen) {
                distinct[count++] = a[i];
            }
            if (set.size() != count || set.isEmpty() || !set.contains(a[i])) {
                return false;
            }
        }
        Object[] objects = set.toArray();
        String[] empty = set.toArray(new String[0]);
        String[] given = new String[n];
        for (int i = 0; i < n; i++) {
            given[i] = "z";
        }
        String[] into = set.toArray(given);
        if (objects.length != count || empty.length != count || !((Object) empty instanceof String[])) {
            return false;
        }
        if (n >= count ? into != given || n > count && into[count] != null : into.length != count || !((Object) into instanceof String[])) {
            return false;
        }
        for (int i = 0; i < count; i++) {
            if (objects[i] != distinct[i] || empty[i] != distinct[i] || into[i] != distinct[i]) {
                return false;
            }
        }
        return true;
    }

    /** {@code iterator()}, which the model does not keep: the JDK call it names. */
    public static boolean iterated(String x) {
        Collection<String> set = new LinkedHashSet<>();
        set.add(x);
        return set.iterator().next() == x;
    }

    /** Runs each method over sampled names (of "", "a", "b", "ab", null) on this JVM; prints "ok" or the first that fails. */
    public static void main(String[] args) {
        String[] names = {"", "a", "b", "ab", null};
        int samples = Integer.parseInt(args[0]);
        Random random = new Random(286);
        for (int s = 0; s < samples; s++) {
            String[] a = new String[random.nextInt(5)];
            for (int i = 0; i < a.length; i++) {
                a[i] = names[random.nextInt(names.length)];
            }
            int n = random.nextInt(5);
            String other = names[random.nextInt(names.length)];
            if (!ordered(a, n) || !iterated(other)) {
                System.out.println("fails: " + java.util.Arrays.toString(a) + " n " + n + " other " + other);
                return;
            }
        }
        System.out.println("ok");
    }
}
