package springwork;

public final class RoleChecks {
    static int names(int code, boolean fluent) {
        int seen = 0;
        for (var authority : RoleApplication.reachable(code, fluent)) {
            int i = 0;
            while (i < 4 && !RoleApplication.name(RoleApplication.prefix(code),i).equals(authority.getAuthority())) i++;
            if (i == 4) return 0;
            seen |= 1 << i;
        }
        int expected = code & 15;
        if ((expected & 1) != 0) expected |= 2;
        if ((expected & 2) != 0) expected |= 12;
        return seen == expected ? 1 : 0;
    }

    public static int legacyNames(int code) { return names(code, false); }
    public static int legacyDecision(int code) { return RoleApplication.decide(code,false,false) == ((code & 11) != 0) ? 1 : 0; }
    public static int fluentNames(int code) { return names(code, true); }
    public static int fluentDecision(int code) { return RoleApplication.decide(code,true,false) == ((code & 11) != 0) ? 1 : 0; }
}
