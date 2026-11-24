public final class JacksonExtended {
    public static boolean fifthLength(int ordinal) {
        if (ordinal<11111 || ordinal>111110) return true;
        String s=JacksonNumbers.input(ordinal);
        boolean old=before.JacksonNumbers.looks(s),now=JacksonNumbers.looks(s);
        return JacksonNumbers.trailing(s) ? !old && now : old==now;
    }
    public static boolean exerciseNegative() {
        return !before.JacksonNumbers.looks("7.e1") && !JacksonNumbers.looks("7.e1")
               && !before.JacksonNumbers.looks(".") && !JacksonNumbers.looks(".");
    }
}
