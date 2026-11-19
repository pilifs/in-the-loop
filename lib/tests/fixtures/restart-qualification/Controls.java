public final class Controls {
    static final class Day {
        final int day;
        Day(int day) { this.day = day; }
    }

    static final class Format {
        static final int WIDTH = "long".equals(System.getProperty("foundation.display", "short")) ? 4 : 2;
    }

    public static int arrayJoin(boolean first) {
        int[] value;
        if (first) value = new int[]{2};
        else value = new int[]{5};
        return value[0];
    }

    public static int calendarJoin(boolean first) {
        Day value;
        if (first) value = new Day(15);
        else value = new Day(16);
        return value.day;
    }

    public static int display() { return Format.WIDTH; }

    public static int divide(int divisor) { return 6 / divisor; }

    public static int average(int divisor, int[] marker) {
        try { return divide(divisor); }
        catch (ArithmeticException e) { marker[0] = 1; return 7; }
    }

    public static int checkedAverage(int divisor) {
        int[] marker = {0};
        return average(divisor, marker);
    }

    public static int handler(int divisor) {
        int[] marker = {0};
        int result = average(divisor, marker);
        return 10 * marker[0] + result;
    }

    public static int message(int divisor) {
        try { return divide(divisor); }
        catch (ArithmeticException e) { return "/ by zero".equals(e.getMessage()) ? 1 : 0; }
    }

    public static void main(String[] args) {
        System.out.printf("array %d %d calendar %d %d display %d%n",
                arrayJoin(true), arrayJoin(false), calendarJoin(true), calendarJoin(false), display());
        for (int divisor = -1; divisor <= 1; divisor++) {
            int[] marker = {0};
            int result = average(divisor, marker);
            String escape;
            try { divide(divisor); escape = "none"; }
            catch (ArithmeticException e) { escape = e.getClass().getName() + "(" + e.getMessage() + ")"; }
            System.out.printf("divisor %d handled %d marker %d escaping %s%n", divisor, result, marker[0], escape);
        }
    }
}
