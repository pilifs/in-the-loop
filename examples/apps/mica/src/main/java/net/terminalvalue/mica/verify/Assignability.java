package net.terminalvalue.mica.verify;

import static net.terminalvalue.mica.verify.VerificationType.NULL;
import static net.terminalvalue.mica.verify.VerificationType.OBJECT;
import static net.terminalvalue.mica.verify.VerificationType.TOP;

/**
 * The subtyping relation of the type checker, {@code isAssignable(From, To)} of JVMS §4.10.1.2, on the
 * verification types of {@link VerificationType}. It is what the checker consults when an instruction's operand
 * must be of a type: when a value is stored, passed, returned, or merged at a branch target against the
 * {@code StackMapTable}.
 */
public final class Assignability {

    private Assignability() {}

    public static boolean isAssignable(VerificationType from, VerificationType to) {
        // isAssignable(X, X), and everything is assignable to top.
        if (from == to || to == TOP) {
            return true;
        }
        // int, float, long and double are assignable to themselves (and top) only.
        if (from == TOP || from.isPrimitive() || to.isPrimitive()) {
            return false;
        }
        // uninitialized and uninitializedThis are assignable to themselves (and top) only: a value whose
        // constructor has not run is not a reference yet, and no instruction but invokespecial <init> may use it.
        if (from.isUninitialized() || to.isUninitialized()) {
            return false;
        }
        // null is assignable to every class, interface and array type.
        if (from == NULL) {
            return true;
        }
        if (to == NULL) {
            return false;
        }
        // Every reference is an Object.
        if (to == OBJECT) {
            return true;
        }
        // The checker does not check interfaces: any class is assignable to any interface type, and
        // invokeinterface checks the receiver at run time. Arrays implement Cloneable and Serializable only.
        if (to.isInterface()) {
            return !from.isArray();
        }
        if (from.isArray() != to.isArray()) {
            return false;
        }
        // Arrays of the same primitive type are the same type (handled above); arrays of references are covariant.
        if (from.isArray()) {
            VerificationType fromElement = from.element();
            VerificationType toElement = to.element();
            if (fromElement.isPrimitive() || toElement.isPrimitive()) {
                return false;
            }
            return isAssignable(fromElement, toElement);
        }
        return from.isSubclassOf(to);
    }
}
