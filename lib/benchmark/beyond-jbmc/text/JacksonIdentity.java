public final class JacksonIdentity {
    public static boolean unchanged(int ordinal) {
        if (ordinal<0 || ordinal>11110) return true;
        String word=JacksonNumbers.input(ordinal);
        return before.JacksonNumbers.looks(word)==JacksonNumbers.looks(word);
    }
    public static boolean fixed() {
        return before.JacksonNumbers.looks("-0.")==JacksonNumbers.looks("-0.");
    }
}
