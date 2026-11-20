package paper;
public final class Paper {
    static int initializations;
    static { initializations++; }
    static final String PAPER = System.getProperty("print.paper", "A4");
    public static String size() { return PAPER; }
}
