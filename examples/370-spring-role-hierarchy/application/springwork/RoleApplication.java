package springwork;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import org.springframework.security.access.hierarchicalroles.RoleHierarchyImpl;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.authorization.AuthorityAuthorizationManager;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

public final class RoleApplication {
    public static String prefix(int code) { return code < 16 ? "ROLE_" : "CUSTOM_PREFIX_"; }
    public static String name(String p, int i) { return p + "ABCD".charAt(i); }

    public static RoleHierarchyImpl hierarchy(String p, boolean fluent, boolean omitEdge) {
        if (fluent) {
            var builder = RoleHierarchyImpl.withRolePrefix(p).role("A").implies("B").role("B");
            return (omitEdge ? builder.implies("C") : builder.implies("C", "D")).build();
        }
        var graph = new RoleHierarchyImpl();
        graph.setHierarchy(p+"A > "+p+"B\n"+p+"B > "+p+"C"+(omitEdge ? "" : "\n"+p+"B > "+p+"D"));
        return graph;
    }

    public static List<GrantedAuthority> authorities(int code) {
        List<GrantedAuthority> input = new ArrayList<>();
        for (int bit = 0; bit < 4; bit++)
            if ((code & (1 << bit)) != 0) input.add(new SimpleGrantedAuthority(name(prefix(code),bit)));
        return input;
    }
    public static Collection<? extends GrantedAuthority> reachable(int code, boolean fluent) {
        return hierarchy(prefix(code), fluent, false).getReachableGrantedAuthorities(authorities(code));
    }
    public static boolean decide(int code, boolean fluent, boolean omitEdge) {
        var manager = AuthorityAuthorizationManager.hasAuthority(prefix(code) + "D");
        manager.setRoleHierarchy(hierarchy(prefix(code), fluent, omitEdge));
        var auth = new TestingAuthenticationToken("user", null, authorities(code));
        return manager.check(() -> auth, new Object()).isGranted();
    }
}
