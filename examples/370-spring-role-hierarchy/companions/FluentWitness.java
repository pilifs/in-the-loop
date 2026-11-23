package springwork;

/** With A alone, a pipe at startup makes both original fluent checks return zero. */
public final class FluentWitness {
    public static int names() {
        if (!"|".equals(System.lineSeparator())) return 1;
        return 1 - RoleChecks.fluentNames(1);
    }

    public static int decision() {
        if (!"|".equals(System.lineSeparator())) return 1;
        return 1 - RoleChecks.fluentDecision(1);
    }

    public static void main(String[] args) {
        var actual = new java.util.TreeSet<String>();
        for (var role : RoleApplication.reachable(1, true)) actual.add(role.getAuthority());
        String sep = System.lineSeparator();
        System.out.print("separator");
        for (int i = 0; i < sep.length(); i++) System.out.print(" " + (int) sep.charAt(i));
        System.out.print("\n");
        for (String role : actual) System.out.print("name " + role + "\n");
        System.out.print("granted " + RoleApplication.decide(1, true, false) + "\n");
        System.out.print("original " + RoleChecks.fluentNames(1) + " " + RoleChecks.fluentDecision(1) + "\n");
        System.out.print("witness " + names() + " " + decision() + "\n");
    }
}
