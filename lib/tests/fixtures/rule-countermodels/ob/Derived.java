package ob;

/** The outside review's countermodel with the other class a superclass: the initializer writes Base.x, then its own. */
public class Derived extends Base {
    public static int k;

    static {
        Base.x = 1;
        k = 7;
    }
}
