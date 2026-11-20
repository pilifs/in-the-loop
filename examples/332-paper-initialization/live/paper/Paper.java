package paper;
public final class Paper {
    static int initializations;
    static { initializations++; }
    
    public static String size() { return System.getProperty("print.paper", "A4"); }
}
