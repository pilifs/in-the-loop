package springwork;

/** The public manager on a fresh authentic hierarchy and authentication for each decision. */
public final class HierarchyEdge {
    private static int decisions(int prefix) {
        int mask = 0;
        if (RoleApplication.decide(prefix + 1, false, false)) mask |= 1;
        if (RoleApplication.decide(prefix + 1, false, true)) mask |= 2;
        if (RoleApplication.decide(prefix + 8, false, true)) mask |= 4;
        if (RoleApplication.decide(prefix + 4, false, false)) mask |= 8;
        return mask;
    }

    public static int role() { return decisions(0); }
    public static int custom() { return decisions(16); }

    public static void main(String[] args) {
        System.out.println("ROLE_ " + role());
        System.out.println("CUSTOM_PREFIX_ " + custom());
    }
}
