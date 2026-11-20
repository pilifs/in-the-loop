package claims;

import java.util.Arrays;
import java.util.Optional;
import java.util.function.IntPredicate;
import java.util.function.Supplier;
import java.util.stream.IntStream;

public final class L {
    private L() {}

    private static final class Fallback implements Supplier<Integer> {
        int calls;
        public Integer get() { calls++; return 7; }
    }

    public static boolean optional(boolean present) {
        Fallback fallback = new Fallback();
        Optional<Integer> value = present ? Optional.of(2) : Optional.empty();
        int answer = value.orElseGet(fallback);
        return answer == (present ? 2 : 7) && fallback.calls == (present ? 0 : 1);
    }

    static boolean any(int[] a, IntPredicate p) {
        for (int x : a) {
            if (p.test(x)) return true;
        }
        return false;
    }

    public static boolean lambda(int[] a, int k) {
        boolean want = false;
        for (int x : a) {
            want |= x > k;
        }
        return any(a, x -> x > k) == want;
    }

    public static boolean streams(String[] a, String f) {
        if (a == null) return true;
        boolean anyEq = false, allNull = true, noneEmpty = true;
        for (String s : a) {
            anyEq |= s != null && s.equals(f);
            allNull &= s == null;
            noneEmpty &= !(s != null && s.isEmpty());
        }
        return Arrays.stream(a).anyMatch(s -> s != null && s.equals(f)) == anyEq
                && Arrays.stream(a).allMatch(s -> s == null) == allNull
                && Arrays.stream(a).noneMatch(s -> s != null && s.isEmpty()) == noneEmpty;
    }

    public static boolean chars(String s) {
        boolean ascii = true;
        for (int i = 0; i < s.length(); i++) {
            ascii &= s.charAt(i) < 128;
        }
        return s.chars().allMatch(c -> c < 128) == ascii && s.chars().anyMatch(c -> c == 'x') == (s.indexOf('x') >= 0);
    }

    /** IntStream.range is the loop from the start up to the end, none where the end is not above it. */
    public static boolean range(int from, int to, int k) {
        if (from < -3 || to > 3) return true;
        boolean all = true, any = false, none = true;
        for (int i = from; i < to; i++) {
            all &= i < k;
            any |= i == k;
            none &= i != k;
        }
        return IntStream.range(from, to).allMatch(i -> i < k) == all
                && IntStream.range(from, to).anyMatch(i -> i == k) == any
                && IntStream.range(from, to).noneMatch(i -> i == k) == none;
    }

    public static boolean mapped(String[] a) {
        if (a == null) return true;
        for (String s : a) {
            if (s == null) return true;
        }
        String[] tails = Arrays.stream(a).map(s -> s.isEmpty() ? s : s.substring(1)).toArray(String[]::new);
        if (tails.length != a.length) return false;
        for (int i = 0; i < a.length; i++) {
            if (tails[i].length() != Math.max(0, a[i].length() - 1)) return false;
        }
        return true;
    }
}
