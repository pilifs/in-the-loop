package fixtures;

/** Overloaded methods: a target names one of them by its parameter types, `fixtures.Overloads#pick(boolean)`. */
public final class Overloads {
    private Overloads() {}

    public static String pick(boolean flag) {
        return flag ? "yes" : "no";
    }

    public static String pick(TrafficLight.Light light) {
        return light.name().toLowerCase();
    }

    public static int twice(int x) {
        return 2 * x;
    }

    public static long twice(long x) {
        return 2L * x;
    }
}
