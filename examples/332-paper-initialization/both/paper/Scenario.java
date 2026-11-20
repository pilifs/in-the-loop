package paper;

public final class Scenario {
    static void set(int code) {
        if (code == 0) System.clearProperty("print.paper");
        else System.setProperty("print.paper", code == 1 ? "A4" : "Letter");
    }

    public static int value(int code) {
        set(code / 3);
        Paper.size();
        set(code % 3);
        return Paper.size().equals("Letter") ? 2 : Paper.size().equals("A4") ? 1 : 0;
    }

    public static int count(int code) {
        value(code);
        return Paper.initializations;
    }
}
