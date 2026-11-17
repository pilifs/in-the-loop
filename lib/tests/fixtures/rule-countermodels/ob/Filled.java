package ob;

/** A class of the interface whose initializer writes a cell of the interface's array, then its own static. */
public class Filled implements Table {
    public static int k;

    static {
        T[0] = 5;
        k = 7;
    }
}
