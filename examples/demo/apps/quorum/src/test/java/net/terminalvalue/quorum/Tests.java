package net.terminalvalue.quorum;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * The test runner: every public static no-argument method of the test classes is a test. Prints one line per
 * failure as {@code FAIL Class.method: message} and exits 1 if any failed. No framework, so that the module builds
 * with {@code javac} alone.
 */
public final class Tests {

    private static final List<Class<?>> CLASSES = List.of(
            net.terminalvalue.quorum.QuorumTest.class,
            net.terminalvalue.quorum.raft.RoleMachineTest.class,
            net.terminalvalue.quorum.raft.VoteRuleTest.class,
            net.terminalvalue.quorum.backoff.BackoffTest.class,
            net.terminalvalue.quorum.clock.HybridLogicalClockTest.class,
            net.terminalvalue.quorum.replication.LastWriterWinsTest.class,
            net.terminalvalue.quorum.twopc.CoordinatorTest.class,
            net.terminalvalue.quorum.twopc.RecoveryTest.class,
            net.terminalvalue.quorum.twopc.NodesTest.class);

    private Tests() {}

    public static void main(String[] args) {
        int run = 0;
        List<String> failures = new ArrayList<>();
        for (Class<?> c : CLASSES) {
            Method[] methods = c.getDeclaredMethods();
            Arrays.sort(methods, (a, b) -> a.getName().compareTo(b.getName()));
            for (Method m : methods) {
                if (!Modifier.isStatic(m.getModifiers()) || !Modifier.isPublic(m.getModifiers()) || m.getParameterCount() != 0) {
                    continue;
                }
                run++;
                try {
                    m.invoke(null);
                } catch (InvocationTargetException e) {
                    String name = c.getSimpleName() + "." + m.getName();
                    failures.add(name);
                    System.out.println("FAIL " + name + ": " + e.getCause());
                } catch (IllegalAccessException e) {
                    throw new IllegalStateException(e);
                }
            }
        }
        System.out.println(run + " tests, " + failures.size() + " failed");
        System.exit(failures.isEmpty() ? 0 : 1);
    }

    public static void check(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    public static void equal(Object expected, Object actual) {
        if (!java.util.Objects.equals(expected, actual)) {
            throw new AssertionError("expected " + expected + " but was " + actual);
        }
    }

    public static void throwsIllegalArgument(Runnable action) {
        try {
            action.run();
        } catch (IllegalArgumentException expected) {
            return;
        }
        throw new AssertionError("expected an IllegalArgumentException");
    }
}
