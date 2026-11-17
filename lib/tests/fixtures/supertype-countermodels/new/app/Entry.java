package app;

/**
 * The same in both versions. Each method reaches a class whose code is the same in both versions and whose
 * supertypes are not: Child extends One in the previous version and Two in the new one, Plain implements Marker in
 * the previous version only, and Mixed takes its default method from Left in the previous version and from Right in
 * the new one. Every method of every class is the same text in both.
 */
public class Entry {
    /** A static method Child inherits: javac names Child, and the JVM resolves it through Child's superclass. */
    public static int rebased(int k) {
        return Child.value(k);
    }

    /** An instanceof of an interface the previous version's Plain implements. */
    public static int marked(int k) {
        Object o = new Plain();
        return k > 1000 ? (o instanceof Marker ? 2 : 1) : 0;
    }

    /** A cast to that interface: the new version's Plain is no Marker, so the cast throws. */
    public static int cast(int k) {
        Object o = new Plain();
        if (k > 1000) {
            Marker m = (Marker) o;
            return m == null ? 0 : 2;
        }
        return 0;
    }

    /** A default method Mixed takes from whichever interface it implements. */
    public static int mixed(int k) {
        return new Mixed().m(k);
    }

    /**
     * The instanceof in a loop past the bound, of an object made in each iteration. Plain is made once before the
     * loop, so that no iteration initializes a class.
     */
    public static int looped(int k) {
        int acc = new Plain() == null ? 1 : 0;
        for (int i = 0; i < k; i++) {
            acc += i > 1000 ? ((Object) new Plain() instanceof Marker ? 2 : 1) : 0;
        }
        return acc;
    }

    public static void main(String[] args) {
        int cast;
        try {
            cast = cast(1001);
        } catch (ClassCastException e) {
            cast = -1;
        }
        System.out.println("rebased=" + rebased(1001) + " marked=" + marked(1001) + " cast=" + cast + " mixed=" + mixed(1001) + " looped=" + looped(1002));
    }
}
