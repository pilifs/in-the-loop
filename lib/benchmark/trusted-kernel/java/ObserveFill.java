import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;

public final class ObserveFill {
    static String sha(Class<?> c) throws Exception {
        try (var stream = c.getResourceAsStream(c.getSimpleName() + ".class")) {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes()));
        }
    }

    static int[] cells(int size, int first) {
        int[] data = new int[size];
        for (int i = 0; i < size; i++) data[i] = first + i;
        return data;
    }

    public static void main(String[] args) throws Exception {
        boolean caller = args[0].equals("caller");
        Class<?> owner = caller ? Class.forName("fill.Range") : Arrays.class;
        Method observe = caller ? owner.getMethod("observe", int[].class, int[].class,
                int.class, int.class, int.class, int.class) : null;
        System.out.println("owner " + sha(owner) + " arrays " + sha(Arrays.class));
        int runs = 0, shared = 0, mismatches = 0, frameMismatches = 0;
        for (int n = 0; n <= 2; n++) {
            for (int from = 0; from <= n; from++) for (int to = from; to <= n; to++) {
                // m=-1 selects the same root. Other roots vary independently, including length zero.
                for (int m = -1; m <= 3; m++) {
                    int observations = caller ? (m < 0 ? n : m) : 1;
                    for (int k = 0; k < observations; k++) {
                        int[] a = cells(n, 11);
                        int[] b = m < 0 ? a : cells(m, 31);
                        int[] old = a.clone();
                        int[] otherOld = b.clone();
                        int wanted = caller ? (m < 0 && from <= k && k < to ? 7 : b[k]) : 0;
                        int got = 0;
                        if (caller) got = (Integer)observe.invoke(null, a, b, from, to, 7, k);
                        else Arrays.fill(a, from, to, 7);
                        boolean frame = true;
                        for (int i = 0; i < n; i++)
                            frame &= a[i] == (from <= i && i < to ? 7 : old[i]);
                        if (m >= 0) for (int i = 0; i < m; i++) frame &= b[i] == otherOld[i];
                        if (!frame) frameMismatches++;
                        if (got != wanted && mismatches++ == 0) {
                            System.out.println("witness " + "shared=" + (m < 0) + " before=" + Arrays.toString(old)
                                + " from=" + from + " to=" + to + " value=7 k=" + k + " expected=" + wanted
                                + " returned=" + got + " after=" + Arrays.toString(a));
                        }
                        runs++;
                        if (m < 0) shared++;
                    }
                }
            }
        }
        System.out.printf("cases %d shared %d distinct %d observed-mismatch %d frame-mismatch %d%n",
            runs, shared, runs - shared, mismatches, frameMismatches);
    }
}
