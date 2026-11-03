package net.terminalvalue.mica.link;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.link.AccessControl.check;
import static net.terminalvalue.mica.link.Relation.SAME_CLASS;
import static net.terminalvalue.mica.link.Relation.SAME_NEST;
import static net.terminalvalue.mica.link.Relation.SAME_PACKAGE;
import static net.terminalvalue.mica.link.Relation.SUBCLASS_IN_OTHER_PACKAGE;
import static net.terminalvalue.mica.link.Relation.UNRELATED;
import static net.terminalvalue.mica.link.Visibility.PACKAGE_PRIVATE;
import static net.terminalvalue.mica.link.Visibility.PRIVATE;
import static net.terminalvalue.mica.link.Visibility.PROTECTED;
import static net.terminalvalue.mica.link.Visibility.PUBLIC;

public final class AccessControlTest {

    private AccessControlTest() {}

    public static void publicMembersAreAccessibleToEveryone() {
        for (Relation r : Relation.values()) {
            check(check(PUBLIC, r, false, false), "public from " + r);
        }
    }

    public static void privateMembersAreAccessibleToTheDeclaringClass() {
        check(check(PRIVATE, SAME_CLASS, false, false), "private from the class");
        check(!check(PRIVATE, SAME_PACKAGE, false, false), "private from the package");
        check(!check(PRIVATE, SUBCLASS_IN_OTHER_PACKAGE, false, true), "private from a subclass");
        check(!check(PRIVATE, UNRELATED, true, false), "private from elsewhere");
    }

    public static void packagePrivateMembersAreAccessibleWithinThePackage() {
        check(check(PACKAGE_PRIVATE, SAME_PACKAGE, false, false), "from the package");
        check(check(PACKAGE_PRIVATE, SAME_NEST, false, false), "from a nestmate, which is in the package");
        check(!check(PACKAGE_PRIVATE, SUBCLASS_IN_OTHER_PACKAGE, false, true), "from a subclass elsewhere");
        check(!check(PACKAGE_PRIVATE, UNRELATED, false, false), "from elsewhere");
    }

    public static void protectedMembersAreAccessibleWithinThePackage() {
        check(check(PROTECTED, SAME_PACKAGE, false, false), "from the package");
        check(check(PROTECTED, SAME_NEST, false, false), "from a nestmate");
        check(!check(PROTECTED, UNRELATED, false, true), "from elsewhere");
        check(!check(PROTECTED, UNRELATED, true, false), "static, from elsewhere");
    }

    public static void aSubclassElsewhereReachesProtectedMembersThroughItsOwnObjects() {
        check(check(PROTECTED, SUBCLASS_IN_OTHER_PACKAGE, false, true), "an instance member on an object of the subclass");
        check(check(PROTECTED, SUBCLASS_IN_OTHER_PACKAGE, true, false), "a static member");
    }
}
