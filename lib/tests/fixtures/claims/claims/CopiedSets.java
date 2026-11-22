package claims;

import java.util.Arrays;
import java.util.Collection;
import java.util.HashSet;
import java.util.Set;

public final class CopiedSets {
    public static boolean independent(boolean changeFirst) {
        // FB and Ea are distinct strings with the same Java hash.
        String[] input = {"FB", null, "Ea", "FB"};
        Set<String> first = new HashSet<>(Arrays.asList(input));
        Set<String> second = new HashSet<>(first);
        input[0] = "changed";
        Set<String> changed = changeFirst ? first : second;
        Set<String> other = changeFirst ? second : first;
        return changed.size() == 3 && changed.remove("FB") && !changed.remove("FB")
            && changed.contains(null) && changed.contains("Ea") && !changed.contains("changed")
            && other.contains("FB") && other.size() == 3 && changed.size() == 2;
    }

    static final class Key {
        int calls, comparisons;
        final boolean throwsOnHash;
        Key(boolean throwsOnHash) { this.throwsOnHash = throwsOnHash; }
        public int hashCode() {
            calls++;
            if (throwsOnHash) throw new IllegalArgumentException();
            return 0;
        }
        public boolean equals(Object other) {
            comparisons++;
            return this == other;
        }
    }

    public static boolean callbacks(boolean fail) {
        Key first = new Key(false);
        Key last = new Key(fail);
        try {
            Set<Key> set = new HashSet<>(Arrays.asList(first, last));
            return !fail && set.size() == 2 && first.calls == 1 && last.calls == 1
                && first.comparisons == 0 && last.comparisons == 1;
        } catch (IllegalArgumentException expected) {
            return fail && first.calls == 1 && last.calls == 1 && last.comparisons == 0;
        }
    }

    public static boolean nullSource() {
        try {
            new HashSet<>((Collection<?>) null);
            return false;
        } catch (NullPointerException expected) { return true; }
    }

    public static boolean retainsDuplicates() {
        return new HashSet<>(Arrays.asList("FB", "Ea", "FB")).size() == 3;
    }

    public static void main(String[] args) {
        if (!independent(false) || !independent(true) || !callbacks(false) || !callbacks(true)
                || !nullSource() || retainsDuplicates()) throw new AssertionError();
    }
}
