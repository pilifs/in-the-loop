package bench.real;

/**
 * The CERT Oracle Coding Standard for Java, NUM00-J, "Detect or prevent integer overflow", on a range check,
 * before the fix: {@code off + len > b.length} overflows for a large {@code len}, so the check passes, and the loop then
 * runs no iteration and returns 0 for a range that is not in the array. JDK 8's
 * {@code java.io.OutputStream.write(byte[], int, int)} also tests {@code (off + len) < 0} for this reason. The fix
 * compares {@code len} with {@code b.length - off}, which cannot overflow.
 */
public final class Checksum {
    private Checksum() {
    }

    public static int sum(byte[] b, int off, int len) {
        if (off < 0 || len < 0 || off + len > b.length) {
            throw new IndexOutOfBoundsException();
        }
        int sum = 0;
        for (int i = off; i < off + len; i++) {
            sum += b[i];
        }
        return sum;
    }
}
