/** Independent finite-domain check of the generated scalar entry and selected observation. */
public final class CheckMapping {
    static int[][] contents = {{}, {0}, {1}, {0, 0}, {0, 1}, {1, 0}, {1, 1}};

    static int[] choices(int code) {
        int[] values = code < 0 ? new int[0] : contents[code];
        return new int[] {values.length, values.length > 0 ? values[0] : 0, values.length > 1 ? values[1] : 0};
    }

    static int check(int left, int right, boolean shared, String projection) {
        int[] l = choices(left);
        int[] r = choices(right);
        boolean admitted = RegressionPair.admitted(l[0], l[1], l[2], r[0], r[1], r[2], left < 0, right < 0, shared);
        boolean agrees = RegressionPair.agree(l[0], l[1], l[2], r[0], r[1], r[2], left < 0, right < 0, shared);
        boolean wrote = l[0] > 0 && r[0] > 0 && l[1] == 0;
        boolean different = wrote && (projection.equals("both-roots") || projection.equals("right-root") && shared);
        if (!admitted || agrees == different) throw new AssertionError(left + "/" + right + " shared=" + shared);
        return different ? 1 : 0;
    }

    public static void main(String[] args) {
        if (RegressionPair.admitted(3, 0, 0, 0, 0, 0, false, false, false)
                || RegressionPair.admitted(1, 2, 0, 0, 0, 0, false, false, false)) {
            throw new AssertionError("outside the input domain");
        }
        int differences = 0;
        int cases = 0;
        for (int l = -1; l < contents.length; l++) {
            for (int r = -1; r < contents.length; r++) {
                differences += check(l, r, false, args[0]);
                cases++;
            }
            if (l >= 0) {
                differences += check(l, l, true, args[0]);
                cases++;
            }
        }
        System.out.println(cases + " " + differences);
    }
}
