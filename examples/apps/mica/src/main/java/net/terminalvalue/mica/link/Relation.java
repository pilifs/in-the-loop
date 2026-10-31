package net.terminalvalue.mica.link;

/**
 * How the class that refers to a member, D, relates to the class that declares it, C. The linker computes the
 * relation from the loaded classes, their run-time packages and their {@code NestHost} and {@code NestMembers}
 * attributes.
 */
public enum Relation {
    /** D is C. */
    SAME_CLASS,
    /** D and C are nestmates: they share a nest host (class file version 55 and later). Nestmates share a package. */
    SAME_NEST,
    /** D and C are in the same run-time package, and not in the same nest. */
    SAME_PACKAGE,
    /** D is a subclass of C, in another package. */
    SUBCLASS_IN_OTHER_PACKAGE,
    /** None of the above. */
    UNRELATED
}
