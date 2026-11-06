package bench.real;

/**
 * FindBugs' bug pattern RV_ABSOLUTE_VALUE_OF_HASHCODE, "Bad attempt to compute absolute value of signed 32-bit
 * hashcode", before the fix: {@code Math.abs(Integer.MIN_VALUE)} is {@code Integer.MIN_VALUE}, so a bucket index taken as
 * {@code Math.abs(hash) % buckets} is negative for that one hash unless the bucket count divides 2^31. The usual
 * fix clears the sign bit instead.
 */
public final class Bucket {
    private Bucket() {
    }

    public static int index(int hash, int buckets) {
        return Math.abs(hash) % buckets;
    }
}
