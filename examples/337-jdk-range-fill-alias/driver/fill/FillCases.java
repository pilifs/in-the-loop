package fill;

import java.util.Arrays;

public final class FillCases {
    public static void main(String[] args) {
        int code = 0;
        for (int length = 0; length <= 3; length++) {
            for (int from = 0; from <= length; from++) {
                for (int to = from; to <= length; to++) {
                    for (boolean alias : new boolean[]{false, true}) {
                        for (int value : new int[]{-1, 9}) {
                            int[] a = new int[length], other = alias ? a : new int[length + 1];
                            for (int i = 0; i < other.length; i++) other[i] = 20 + i;
                            for (int i = 0; i < a.length; i++) a[i] = 4 + i;
                            int[] oldA = a.clone(), oldOther = other.clone();
                            int size = Range.apply(a, other, from, to, value);
                            int[] seen = new int[other.length];
                            for (int k = 0; k < seen.length; k++) {
                                int[] fresh = oldA.clone();
                                seen[k] = Range.observe(fresh, alias ? fresh : oldOther.clone(), from, to, value, k);
                            }
                            System.out.printf("{\"id\":%d,\"from\":%d,\"to\":%d,\"value\":%d,\"alias\":%b,"
                                    + "\"a\":%s,\"other\":%s,\"result\":%d,\"after\":%s,\"otherAfter\":%s,\"seen\":%s}%n",
                                    code++, from, to, value, alias, Arrays.toString(oldA), Arrays.toString(oldOther),
                                    size, Arrays.toString(a), Arrays.toString(other), Arrays.toString(seen));
                        }
                    }
                }
            }
        }
    }
}
