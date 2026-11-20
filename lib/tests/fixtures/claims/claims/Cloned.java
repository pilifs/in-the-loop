package claims;

/**
 * An object a JDK call makes of a class below the one its descriptor declares: {@code Object.clone()} of this class,
 * declared to return {@code Object}, returns a {@code Cloned}. Under {@code --gaps assume} the call is taken to return
 * "a new object", whose class the engine does not know: what that class would decide is refused, and what the
 * declared class settles is not. {@code main} prints what a JVM says of each.
 */
public final class Cloned implements Cloneable {
    static int printed;
    int number;
    int[] cell;

    public static boolean shallow() {
        Cloned first = new Cloned();
        first.number = 3;
        first.cell = new int[]{1};
        Cloned second = (Cloned) first.copy();
        second.number++;
        second.cell[0] = 7;
        return second != first && second.number == 4 && first.number == 3 && second.cell == first.cell && first.cell[0] == 7;
    }

    @Override
    public String toString() {
        printed++;
        return "cloned";
    }

    Object copy() {
        try {
            return super.clone();
        } catch (CloneNotSupportedException e) {
            throw new IllegalStateException(e);
        }
    }

    /** The copy's {@code toString} is this class's, which counts: false on a JVM, so no check may prove it. */
    public static boolean printsNothing() {
        printed = 0;
        Object copy = new Cloned().copy();
        copy.toString();
        return printed == 0;
    }

    /** The copy is a {@code Cloned}, so a {@code Cloneable}: false on a JVM. */
    public static boolean notCloneable() {
        return !(new Cloned().copy() instanceof Cloneable);
    }

    /** What the declared class settles: the copy is an {@code Object}. True on a JVM. */
    public static boolean anObject() {
        return new Cloned().copy() instanceof Object;
    }

    public static void main(String[] args) {
        if (!shallow()) throw new AssertionError();
        System.out.println("printsNothing=" + printsNothing() + " notCloneable=" + notCloneable() + " anObject=" + anObject());
    }
}
