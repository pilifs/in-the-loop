package app;

/**
 * The same in both versions. Each method reaches code the versions change in a way the shared reach does not follow:
 * an override the new version removed (Square), an interface's initializer run by a read through a class that
 * implements it (Limits, through Impl), a superinterface's initializer run when an object is made (Tagged), and a
 * field the previous version declared that hides an inherited one (Box). Own's initializer is the fifth.
 */
public class Entry {
    /** A virtual call on a Square: the previous version's Square declares area, the new one inherits Base's. */
    public static int removed(int k) {
        return new Square().area(k);
    }

    /** A static field the interface Limits declares, read through Impl: reading it initializes Limits. */
    public static int constant(int k) {
        return k > 1000 ? Impl.LIMIT : 0;
    }

    /** Making an Item initializes Tagged, which declares a default method, and its initializer sets Counter.v. */
    public static int defaulted(int k) {
        new Item();
        return k > 1000 ? Counter.v : 0;
    }

    /** A field read through Box: the previous version's Box declares its own x, which hides Holder's. */
    public static int hidden(int k) {
        Box b = new Box();
        return k > 1000 ? b.x : 0;
    }

    /** The read through Impl in a loop past the bound, with Limits initialized before the loop. */
    public static int looped(int k) {
        int acc = Impl.LIMIT - Impl.LIMIT;
        for (int i = 0; i < k; i++) {
            acc += i > 1000 ? Impl.LIMIT : 0;
        }
        return acc;
    }

    public static void main(String[] args) {
        System.out.println("removed=" + removed(1001) + " constant=" + constant(1001) + " defaulted=" + defaulted(1001) + " hidden=" + hidden(1001) + " own=" + Own.f(1001)
            + " looped=" + looped(1002));
    }
}
