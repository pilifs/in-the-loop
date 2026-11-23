public final class ArrayStores {
    static int store(Object[] values, int index, Object replacement) {
        try { values[index] = replacement; return 0; }
        catch (NullPointerException e) { return 1; }
        catch (ArrayIndexOutOfBoundsException e) { return 2; }
        catch (ArrayStoreException e) { return 3; }
    }
    public static boolean history(int index, int kind, boolean absent) {
        String old = "old";
        String[] typed = {old};
        Object replacement = kind == 0 ? "new" : kind == 1 ? null : new Object();
        int outcome = store(absent ? null : typed, index, replacement);
        int wanted = absent ? 1 : index != 0 ? 2 : kind == 0 || kind == 1 ? 0 : 3;
        return outcome == wanted && typed[0] == (wanted == 0 ? replacement : old);
    }
    public static boolean alwaysSucceeds() { return store(new String[]{"old"}, 0, new Object()) == 0; }
}
