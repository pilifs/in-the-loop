package springwork;

import java.util.TreeSet;
import org.springframework.security.access.hierarchicalroles.RoleHierarchyImpl;
import static org.intheloop.controls.Grid.*;

public final class Cases {
    static Object names(int code, boolean fluent) {
        TreeSet<String> result = new TreeSet<>();
        for (var auth : RoleApplication.reachable(code,fluent)) result.add(auth.getAuthority());
        return result;
    }
    public static void main(String[] args) {
        boolean builder;
        try { RoleHierarchyImpl.class.getMethod("withRolePrefix", String.class); builder = true; }
        catch (NoSuchMethodException absent) { builder = false; }
        for (int code : new int[]{1, 2, 17, 18})
            if (!RoleApplication.decide(code,false,false) || RoleApplication.decide(code,false,true)
                    || builder && RoleApplication.decide(code,true,true)) throw new AssertionError("missing B to D edge");
        for (int code = 0; code < 32; code++) {
            row(code,fields("prefix",RoleApplication.prefix(code),"subset",code & 15),
                fields("api",builder ? "present" : "absent","legacyNames",names(code,false),
                    "legacyDecision",RoleApplication.decide(code,false,false),"fluentNames",builder ? names(code,true) : null,
                    "fluentDecision",builder ? RoleApplication.decide(code,true,false) : null),
                fields("legacyNames",RoleChecks.legacyNames(code),"legacyDecision",RoleChecks.legacyDecision(code),
                       "fluentNames",builder ? RoleChecks.fluentNames(code) : 1,"fluentDecision",builder ? RoleChecks.fluentDecision(code) : 1));
        }
    }
}
