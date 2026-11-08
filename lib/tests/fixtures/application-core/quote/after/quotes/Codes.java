package quotes;

/** What a request's code says. */
public final class Codes {
    private Codes() {
    }

    /** Whether the code is a VIP's: it starts with "VIP". */
    public static boolean vip(String code) {
        return code.length() >= 3 && code.charAt(0) == 'V' && code.charAt(1) == 'I' && code.charAt(2) == 'P';
    }
}
