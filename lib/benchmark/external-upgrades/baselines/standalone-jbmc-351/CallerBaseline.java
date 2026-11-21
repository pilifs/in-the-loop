public final class CallerBaseline {
    public static void check(boolean selected) {
        boolean matches;
        try {

        long millis = calibration.Projection.roundtrip(selected);
        matches = millis == (selected ? 946684800123L : Long.MAX_VALUE);
        } catch (Throwable error) {
            matches = false;
        }
        assert matches : "original caller observation";
    }
    public static void main(String[] args) { check(Boolean.parseBoolean(args[0])); }
}
