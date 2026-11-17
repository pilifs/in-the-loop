package claims;

import java.util.HashSet;
import java.util.Random;
import java.util.Set;

/**
 * A {@code HashSet} of names, as Spring's {@code AbstractBindingResult} records the fields it suppressed (example
 * 286): each method returns whether the set does what the JDK documents, written out over {@code equals}, so a proof
 * of {@code result} with {@code --model java.util.HashSet} is a proof that the model and the definition agree on every
 * input of the bound, and {@code main} runs the same methods on a JVM over sampled inputs, on the JDK's set.
 */
public class Sets {
    /**
     * Added in order: each {@code add} true exactly when no earlier name equals it, the size the number of distinct
     * names, each name contained, and {@code other} contained exactly when one of them equals it.
     */
    public static boolean added(String[] a, String other) {
        Set<String> set = new HashSet<>();
        if (!set.isEmpty() || set.size() != 0 || set.contains(other)) {
            return false;
        }
        int distinct = 0;
        for (int i = 0; i < a.length; i++) {
            boolean seen = false;
            for (int j = 0; j < i; j++) {
                seen |= a[j] == null ? a[i] == null : a[j].equals(a[i]);
            }
            if (set.add(a[i]) == seen) {
                return false;
            }
            if (!seen) {
                distinct++;
            }
            if (set.size() != distinct || set.isEmpty() || !set.contains(a[i])) {
                return false;
            }
        }
        boolean among = false;
        for (int i = 0; i < a.length; i++) {
            among |= a[i] == null ? other == null : a[i].equals(other);
        }
        return set.contains(other) == among;
    }

    /** {@code remove}, which the model does not keep: the JDK call it names. */
    public static boolean removed(String x) {
        Set<String> set = new HashSet<>();
        set.add(x);
        return set.remove(x) && set.isEmpty();
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
            String other = names[random.nextInt(names.length)];
            if (!added(a, other) || !removed(other)) {
                System.out.println("fails: " + java.util.Arrays.toString(a) + " other " + other);
                return;
            }
        }
        System.out.println("ok");
    }
}
