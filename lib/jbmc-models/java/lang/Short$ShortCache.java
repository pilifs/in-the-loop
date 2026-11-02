package java.lang;

/**
 * A model of the JDK's {@code java.lang.Short.ShortCache} for JBMC. The real class sizes its cache from a VM property
 * (or the CDS archive), which JBMC has no bytecode for: the upper bound becomes a nondeterministic int, the cache a
 * nondeterministic array, and {@code Short.valueOf} an {@code ArrayIndexOutOfBoundsException} on inputs the real
 * cache covers. The model declares an empty range, so {@code valueOf} allocates a fresh object for every value, as
 * the CProver models library's own {@code Short.valueOf} does: identity of boxed small values ({@code ==}) is the
 * one observable difference.
 */
final class Short$ShortCache {
    static final int low;
    static final int high;
    static final Short[] cache;

    static {
        low = -128;
        high = -129; // assigned here, not as a ConstantValue, which JBMC does not read
        cache = new Short[0];
    }

    private Short$ShortCache() {
    }
}
