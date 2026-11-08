package quotes;

/** What a request's code says. */
public final class Codes {
    private Codes() {
    }

    /** Whether the code is a VIP's: it starts with "VIP". */
    public static boolean vip(String code) {
        return code.startsWith("VIP");
    }
}
