package springwork;

/** A launch witness for the premise of the native fluent proof, on the same JVM as the public calls. */
public final class FluentLaunch {
    private static String units(String value) {
        var text = new StringBuilder();
        for (int i = 0; i < value.length(); i++) text.append(' ').append((int) value.charAt(i));
        return text.toString();
    }

    public static void main(String[] args) {
        String initial = System.lineSeparator();
        String property = System.setProperty("line.separator", "changed after launch");
        try {
            if (!initial.equals(property) || System.lineSeparator() != initial
                    || !"changed after launch".equals(System.getProperty("line.separator"))) throw new AssertionError();
            boolean active = "\n".equals(System.lineSeparator()) || "\r\n".equals(System.lineSeparator());
            System.out.print("startup" + units(initial) + "\nproperty" + units(property) + "\nactive " + (active ? 1 : 0) + "\n");
            for (int code = 0; code < 32; code++) {
                System.out.print(code + " " + RoleChecks.fluentNames(code) + " " + RoleChecks.fluentDecision(code)
                        + " " + FluentLines.check(code) + "\n");
            }
        } finally {
            System.setProperty("line.separator", property);
        }
    }
}
