package net.terminalvalue.mica.link;

/**
 * Access control for a field or method reference, JVMS §5.4.4: whether a member R declared in class C is
 * accessible to the class D whose code refers to it, as resolution checks it (and as the type checker checks the
 * receiver of a protected instance member, §4.10.1.8).
 */
public final class AccessControl {

    private AccessControl() {}

    /**
     * @param member               the visibility of R
     * @param relation             how D relates to C
     * @param staticMember         whether R is static
     * @param objectrefIsCurrentOrSubclass for an instance member, whether the type of the object the reference is
     *                             applied to is D or a subclass of D; irrelevant for a static member
     */
    public static boolean check(Visibility member, Relation relation, boolean staticMember, boolean objectrefIsCurrentOrSubclass) {
        return switch (member) {
            case PUBLIC -> true;
            // Nest-based access control (JEP 181) is not implemented yet: nestmates reach each other's private
            // members through the synthetic accessors javac generates for class files before version 55.
            case PRIVATE -> relation == Relation.SAME_CLASS;
            case PACKAGE_PRIVATE -> relation == Relation.SAME_CLASS || relation == Relation.SAME_NEST || relation == Relation.SAME_PACKAGE;
            case PROTECTED -> switch (relation) {
                case SAME_CLASS, SAME_NEST, SAME_PACKAGE -> true;
                // A subclass elsewhere reaches a protected instance member only through its own objects: the
                // objectref must be of D or a subclass of D, not just any C.
                case SUBCLASS_IN_OTHER_PACKAGE -> staticMember || objectrefIsCurrentOrSubclass;
                case UNRELATED -> false;
            };
        };
    }
}
