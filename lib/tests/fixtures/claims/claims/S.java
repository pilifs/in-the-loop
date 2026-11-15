package claims;

public final class S {
    private S() {}

    public static boolean starts(String s, String p) {
        return s.startsWith(p);
    }

    public static int count(String[] a) {
        int n = 0;
        for (String s : a) {
            if (s != null && s.isEmpty()) {
                n++;
            }
        }
        return n;
    }

    public static String tail(String s) {
        return s.substring(1);
    }

    public static boolean ends(String s) {
        return s.endsWith("x") == (s.length() > 0 && s.charAt(s.length() - 1) == 'x');
    }
}
