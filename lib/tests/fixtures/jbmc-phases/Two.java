public class Two {
    // Two assertions no single input fails together: JBMC solves once per failed one.
    public static int split(int x) {
        if (x > 0) { assert x != 7; } else { assert x != -7; }
        return x;
    }
}
