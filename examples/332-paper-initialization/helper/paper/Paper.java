package paper;
public final class Paper {
    static int initializations;
    static { initializations++; }
    private static String read() { return System.getProperty("print.paper", "A4"); }
    static final String PAPER = read();
    public static String size() { return PAPER; }
}
