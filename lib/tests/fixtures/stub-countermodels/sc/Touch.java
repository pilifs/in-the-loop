package sc;

/** A method framed by an empty write set (`--writes ''`) that writes, through the setter, a bean a static holds. */
public class Touch {
    static final Bean HELD = new Bean();

    public static int touch(int v) {
        HELD.setLevel(v);
        return v;
    }
}
