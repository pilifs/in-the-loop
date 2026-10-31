package net.terminalvalue.mica.verify;

/**
 * The verification types the type checker works with (JVMS §4.10.1.2), over a small class hierarchy: the
 * primitive categories, {@code null}, the two uninitialized types, a few classes, an interface, and arrays.
 * {@code TOP} is the type of a value the checker knows nothing about, the top of the lattice.
 */
public enum VerificationType {
    TOP,
    INT,
    FLOAT,
    LONG,
    DOUBLE,
    /** The type of {@code aconst_null}. */
    NULL,
    /** {@code this} in a constructor before the superclass constructor has run. */
    UNINITIALIZED_THIS,
    /** The object a {@code new} instruction created, before its constructor has run. */
    UNINITIALIZED,
    OBJECT,
    /** {@code java.lang.Runnable}, an interface. */
    RUNNABLE,
    STRING,
    THROWABLE,
    EXCEPTION,
    INT_ARRAY,
    STRING_ARRAY,
    OBJECT_ARRAY;

    public boolean isPrimitive() {
        return this == INT || this == FLOAT || this == LONG || this == DOUBLE;
    }

    public boolean isUninitialized() {
        return this == UNINITIALIZED_THIS || this == UNINITIALIZED;
    }

    public boolean isInterface() {
        return this == RUNNABLE;
    }

    public boolean isArray() {
        return this == INT_ARRAY || this == STRING_ARRAY || this == OBJECT_ARRAY;
    }

    /** The component type of an array type. */
    public VerificationType element() {
        return switch (this) {
            case INT_ARRAY -> INT;
            case STRING_ARRAY -> STRING;
            case OBJECT_ARRAY -> OBJECT;
            default -> throw new IllegalArgumentException(this + " is not an array type");
        };
    }

    /** The direct superclass of a class type, or {@code null} for {@code Object} and for types that are no class. */
    public VerificationType superclass() {
        return switch (this) {
            case STRING, THROWABLE, RUNNABLE -> OBJECT;
            case EXCEPTION -> THROWABLE;
            default -> null;
        };
    }

    /** Whether this class type is {@code other} or one of its subclasses, by the superclass chain. */
    public boolean isSubclassOf(VerificationType other) {
        for (VerificationType t = this; t != null; t = t.superclass()) {
            if (t == other) {
                return true;
            }
        }
        return false;
    }
}
