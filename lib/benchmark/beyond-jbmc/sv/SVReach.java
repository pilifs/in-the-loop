public final class SVReach {
    public static void afterMain() {
        try {
            Main.main(new String[0]);
        } catch (AssertionError reachedOriginalAssertion) {
            // Either a normal return or an original assertion reaches this control.
        }
        assert false;
    }
}
