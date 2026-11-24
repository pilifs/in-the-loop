/** The specified property is the original assert, including paths that terminate on another exception. */
public final class PublicAssertion {
    public static boolean holds() {
        try {
            Main.main(new String[0]);
            return true;
        } catch (AssertionError assertion) {
            return false;
        } catch (Throwable terminated) {
            return true;
        }
    }
}
