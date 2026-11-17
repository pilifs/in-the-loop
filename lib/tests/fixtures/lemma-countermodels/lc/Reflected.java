package lc;

/** A static field read by reflection. */
public final class Reflected {
    static int level;

    public static int reflected() throws ReflectiveOperationException {
        return Reflected.class.getDeclaredField("level").getInt(null);
    }
}
