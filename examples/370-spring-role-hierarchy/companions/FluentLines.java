package springwork;

/** The two original fluent public claims, whenever println writes LF or CRLF. */
public final class FluentLines {
    public static int check(int code) {
        String separator = System.lineSeparator();
        if (!"\n".equals(separator) && !"\r\n".equals(separator)) return 1;
        return RoleChecks.fluentNames(code) & RoleChecks.fluentDecision(code);
    }

    public static void main(String[] args) {
        // Always run the original, unguarded entries on the physical JVM, including
        // the custom-separator control. Use explicit LF for the measurement file.
        String sep = System.lineSeparator();
        System.out.print("separator");
        for (int i = 0; i < sep.length(); i++) System.out.print(" " + (int) sep.charAt(i));
        System.out.print("\n");
        for (int code = 0; code < 32; code++) {
            System.out.print(code + " " + RoleChecks.fluentNames(code) + " "
                    + RoleChecks.fluentDecision(code) + " " + check(code) + "\n");
        }
    }
}
