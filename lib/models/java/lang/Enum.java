package java.lang;

import java.io.Serializable;

/**
 * A model of the JDK's {@code java.lang.Enum} for JBMC, which has no bytecode for it: an enum constant's
 * constructor calls {@code Enum.<init>(String, int)}, which JBMC stubbed as a constructor that sets nothing, and
 * {@code name()} and {@code ordinal()} were stubs that return any value.
 *
 * <p>Kept, as the JDK has them: the two fields, the constructor that sets them (the name is the very string it is
 * given, so {@code name() == name()}), {@code name()}, {@code ordinal()}, {@code toString()} (the name) and
 * {@code equals} (identity). Left out, so that JBMC stubs them as before and the gap scan names them:
 * {@code compareTo} (the JDK's throws {@code ClassCastException} for constants of two enum classes, which needs
 * {@code Class}), {@code hashCode} (the JDK's is the identity hash, as {@code Object}'s), {@code getDeclaringClass},
 * {@code describeConstable}, {@code valueOf(Class, String)} (reflection), {@code clone} and serialization.
 *
 * <p>The interpreter keeps its own natives for {@code Enum}, which behave the same (the conformance corpus checks
 * both against a JVM): an enum's state there is part of every instance it allocates.
 */
public abstract class Enum<E extends Enum<E>> implements Comparable<E>, Serializable {
    private final String name;
    private final int ordinal;

    protected Enum(String name, int ordinal) {
        this.name = name;
        this.ordinal = ordinal;
    }

    public final String name() {
        return name;
    }

    public final int ordinal() {
        return ordinal;
    }

    public String toString() {
        return name;
    }

    public final boolean equals(Object other) {
        return this == other;
    }
}
