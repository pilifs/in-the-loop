package app;

/** What the caller does with an Error the shared code raises: the previous version answers -1, the new one -2. */
public final class Entry {
    private Entry() {}

    public static int kept(int k) {
        try {
            return Shared.kept(k);
        } catch (OutOfMemoryError e) {
            return -1;
        }
    }

    public static int around(int k) {
        try {
            return Shared.around(k);
        } catch (StackOverflowError e) {
            return -1;
        }
    }

    public static void main(String[] args) {
        System.out.println("kept=" + kept(1) + " around=" + around(100_000_000));
    }
}
