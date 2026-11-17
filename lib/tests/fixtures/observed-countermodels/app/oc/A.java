package oc;

/** The outside review's countermodel: an initializer that writes another class's static, then its own. */
public class A {
    public static int k;

    static {
        B.x = 1;
        k = 7;
    }
}
