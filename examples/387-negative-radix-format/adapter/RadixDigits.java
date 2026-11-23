public final class RadixDigits {
    static char digit(int n) { return (char) (n < 10 ? '0' + n : 'a' + n - 10); }
    public static boolean hex(int n) {
        String s = Integer.toString(-n, 16);
        return s.length() == 3 && s.charAt(0) == '-' && s.charAt(1) == digit(n >>> 4) && s.charAt(2) == digit(n & 15);
    }
    public static boolean lowFirst(int n) { return Integer.toString(-n, 16).charAt(1) == digit(n & 15); }
}
