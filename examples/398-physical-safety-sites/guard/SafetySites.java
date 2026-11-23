public final class SafetySites {
    static int run(int mode, int value) {
        if (mode < 0 || mode > 3) return -99;
        if (mode == 0) {
            try { return 18 / value; }
            catch (ArithmeticException expected) { return -10; }
        }
        if (mode == 1) {
            int[] scores = {3, 4};
            return scores[value];
        }
        if (mode == 3) {
            int[] dead = null;
            return dead.length;
        }
        int sum = 0;
        for (int i = 0; i < 7; i++) sum += i;
        return sum;
    }
    public static void caught(int value) {
        if (value == 0) assert run(0, value) == -10;
    }
    public static void caughtMutant(int value) {
        if (value == 0) assert run(0, value) != -10;
    }
    public static void escaping(int value) {
        if (value >= 0 && value <= 2) { int result = run(1, value); assert result > 0; }
    }
    public static void dead(int mode) {
        if (mode == 3) assert run(mode, 0) == -99;
    }
    public static void loop() { assert run(2, 0) == 21; }
    public static void main(String[] args) {
        int mode = Integer.parseInt(args[0]), value = Integer.parseInt(args[1]);
        try { System.out.println("returned " + run(mode,value)); }
        catch (RuntimeException e) { System.out.println("escaped " + e.getClass().getName()); }
    }
}
