public final class JacksonPartition {
    public static boolean changed(int ordinal) {
        if (ordinal<0 || ordinal>11110) return true;
        String s=JacksonNumbers.input(ordinal);
        boolean old=before.JacksonNumbers.looks(s);
        boolean now=JacksonNumbers.looks(s);
        return JacksonNumbers.trailing(s) ? (!old && now) : (old==now);
    }
    public static boolean nullControl() { return !before.JacksonNumbers.looks(null) && !JacksonNumbers.looks(null); }
}
