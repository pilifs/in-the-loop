package springwork;

import org.springframework.util.ConcurrentReferenceHashMap;

/** Exercise the segmented soft-entry cache that ResolvableType purges during formatter startup. */
public final class SoftCache {
    public static int check() {
        var cache = new ConcurrentReferenceHashMap<String, Object>(16, 0.75f, 1);
        var value = new Object();
        if (cache.put("key", value) != null) return 0;
        cache.purgeUnreferencedEntries();
        var first = cache.get("key");
        cache.purgeUnreferencedEntries();
        var second = cache.get("key");
        return (first == null || first == value) && (second == null || second == value)
            && (first != null || second == null) ? 1 : 0;
    }

    private static final class Observed extends ConcurrentReferenceHashMap<String, Object> {
        private Entry<String, Object> retained;

        @Override protected ReferenceManager createReferenceManager() {
            return new ReferenceManager() {
                @Override public Reference<String, Object> createReference(Entry<String, Object> entry,
                        int hash, Reference<String, Object> next) {
                    retained = entry;
                    return super.createReference(entry, hash, next);
                }
            };
        }

        void exercise() {
            var value = new Object();
            put("key", value);
            var reference = getReference("key", Restructure.NEVER);
            if (retained == null || reference.get() != retained) throw new AssertionError("missing registered entry");
            purgeUnreferencedEntries();
            if (get("key") != value || size() != 1) throw new AssertionError("retained");
            reference.release();
            purgeUnreferencedEntries();
            if (get("key") != null || size() != 0) throw new AssertionError("released");
            java.lang.ref.Reference.reachabilityFence(retained);
        }
    }

    public static void main(String[] args) {
        new Observed().exercise();
        System.out.println(check() + " retained=1 released=0");
    }
}
