public final class CallerBaseline {
    public static void check(boolean selected) {
        boolean matches;
        try {

        int[] keys = calibration.GeneratedKeys.keys(selected);
        boolean two = keys != null && keys.length == 2 && keys[0] == 1 && keys[1] == 2;
        boolean last = keys != null && keys.length == 1 && keys[0] == 2;
        matches = selected ? last : two;
        } catch (Throwable error) {
            matches = false;
        }
        assert matches : "original caller observation";
    }
    public static void main(String[] args) { check(Boolean.parseBoolean(args[0])); }
}
