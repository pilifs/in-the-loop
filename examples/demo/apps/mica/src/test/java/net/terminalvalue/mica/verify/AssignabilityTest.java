package net.terminalvalue.mica.verify;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.verify.Assignability.isAssignable;
import static net.terminalvalue.mica.verify.VerificationType.DOUBLE;
import static net.terminalvalue.mica.verify.VerificationType.EXCEPTION;
import static net.terminalvalue.mica.verify.VerificationType.FLOAT;
import static net.terminalvalue.mica.verify.VerificationType.INT;
import static net.terminalvalue.mica.verify.VerificationType.INT_ARRAY;
import static net.terminalvalue.mica.verify.VerificationType.LONG;
import static net.terminalvalue.mica.verify.VerificationType.NULL;
import static net.terminalvalue.mica.verify.VerificationType.OBJECT;
import static net.terminalvalue.mica.verify.VerificationType.OBJECT_ARRAY;
import static net.terminalvalue.mica.verify.VerificationType.RUNNABLE;
import static net.terminalvalue.mica.verify.VerificationType.STRING;
import static net.terminalvalue.mica.verify.VerificationType.STRING_ARRAY;
import static net.terminalvalue.mica.verify.VerificationType.THROWABLE;
import static net.terminalvalue.mica.verify.VerificationType.TOP;
import static net.terminalvalue.mica.verify.VerificationType.UNINITIALIZED;
import static net.terminalvalue.mica.verify.VerificationType.UNINITIALIZED_THIS;

public final class AssignabilityTest {

    private AssignabilityTest() {}

    public static void everyTypeIsAssignableToItselfAndToTop() {
        for (VerificationType t : VerificationType.values()) {
            check(isAssignable(t, t), t + " to itself");
            check(isAssignable(t, TOP), t + " to top");
        }
    }

    public static void primitivesAreAssignableToThemselvesOnly() {
        check(!isAssignable(INT, FLOAT), "int to float");
        check(!isAssignable(LONG, DOUBLE), "long to double");
        check(!isAssignable(INT, OBJECT), "int to Object");
        check(!isAssignable(NULL, INT), "null to int");
        check(!isAssignable(TOP, INT), "top to int");
    }

    public static void nullIsAssignableToEveryReferenceType() {
        check(isAssignable(NULL, OBJECT), "null to Object");
        check(isAssignable(NULL, STRING), "null to String");
        check(isAssignable(NULL, RUNNABLE), "null to Runnable");
        check(isAssignable(NULL, INT_ARRAY), "null to int[]");
        check(!isAssignable(STRING, NULL), "String to null");
    }

    public static void classesFollowTheSuperclassChain() {
        check(isAssignable(STRING, OBJECT), "String to Object");
        check(isAssignable(EXCEPTION, THROWABLE), "Exception to Throwable");
        check(isAssignable(EXCEPTION, OBJECT), "Exception to Object");
        check(!isAssignable(THROWABLE, EXCEPTION), "Throwable to Exception");
        check(!isAssignable(STRING, THROWABLE), "String to Throwable");
    }

    public static void theCheckerTreatsAnInterfaceLikeObject() {
        check(isAssignable(STRING, RUNNABLE), "String to Runnable: invokeinterface checks at run time");
        check(isAssignable(RUNNABLE, OBJECT), "Runnable to Object");
        check(!isAssignable(INT_ARRAY, RUNNABLE), "int[] to Runnable");
    }

    public static void arraysAreCovariantInReferenceElementsOnly() {
        check(isAssignable(INT_ARRAY, OBJECT), "int[] to Object");
        check(isAssignable(STRING_ARRAY, OBJECT_ARRAY), "String[] to Object[]");
        check(!isAssignable(OBJECT_ARRAY, STRING_ARRAY), "Object[] to String[]");
        check(!isAssignable(INT_ARRAY, OBJECT_ARRAY), "int[] to Object[]");
        check(!isAssignable(OBJECT_ARRAY, STRING), "Object[] to String");
        check(!isAssignable(STRING, STRING_ARRAY), "String to String[]");
    }

    public static void uninitializedValuesAreTheirOwnTypes() {
        check(isAssignable(UNINITIALIZED, UNINITIALIZED), "uninitialized to itself");
        check(isAssignable(UNINITIALIZED_THIS, TOP), "uninitializedThis to top");
        check(!isAssignable(UNINITIALIZED, UNINITIALIZED_THIS), "uninitialized to uninitializedThis");
        check(!isAssignable(NULL, UNINITIALIZED), "null to uninitialized");
    }
}
