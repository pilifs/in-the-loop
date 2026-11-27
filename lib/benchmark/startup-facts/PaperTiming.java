package paper;

/** Mark only the second public call, after the caller changes the setting. */
public class PaperTiming {
    public static String second() { return Paper.size(); }
    public static void main(String[] args) {
        int code = Integer.parseInt(args[0]);
        Scenario.set(code / 3);
        String first = Paper.size();
        Scenario.set(code % 3);
        String second = second();
        System.out.println(first + "|" + second + "|" + Paper.initializations);
    }
}
