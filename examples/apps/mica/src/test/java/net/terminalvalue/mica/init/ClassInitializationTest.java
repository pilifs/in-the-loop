package net.terminalvalue.mica.init;

import static net.terminalvalue.mica.Tests.check;
import static net.terminalvalue.mica.Tests.equal;
import static net.terminalvalue.mica.init.InitEffect.NOTIFY_ALL;
import static net.terminalvalue.mica.init.InitEffect.PROCEED;
import static net.terminalvalue.mica.init.InitEffect.RETHROW;
import static net.terminalvalue.mica.init.InitEffect.RUN_INITIALIZER;
import static net.terminalvalue.mica.init.InitEffect.THROW_NO_CLASS_DEF_FOUND_ERROR;
import static net.terminalvalue.mica.init.InitEffect.WAIT;
import static net.terminalvalue.mica.init.InitEffect.WRAP_IN_EXCEPTION_IN_INITIALIZER_ERROR;
import static net.terminalvalue.mica.init.InitState.ERRONEOUS;
import static net.terminalvalue.mica.init.InitState.INITIALIZED;
import static net.terminalvalue.mica.init.InitState.IN_PROGRESS;
import static net.terminalvalue.mica.init.InitState.UNINITIALIZED;

import java.util.List;
import net.terminalvalue.mica.Decision;
import net.terminalvalue.mica.Decision.Transition;
import net.terminalvalue.mica.init.InitEvent.Completed;
import net.terminalvalue.mica.init.InitEvent.Failed;
import net.terminalvalue.mica.init.InitEvent.Request;

public final class ClassInitializationTest {

    private ClassInitializationTest() {}

    public static void theFirstRequestRunsTheInitializer() {
        equal(new Transition<>(IN_PROGRESS, List.of(RUN_INITIALIZER)), ClassInitialization.decide(UNINITIALIZED, new Request(false)));
    }

    public static void anotherThreadWaitsForTheInitializer() {
        equal(new Transition<>(IN_PROGRESS, List.of(WAIT)), ClassInitialization.decide(IN_PROGRESS, new Request(false)));
    }

    public static void theInitializingThreadProceedsOnARecursiveRequest() {
        equal(new Transition<>(IN_PROGRESS, List.of(PROCEED)), ClassInitialization.decide(IN_PROGRESS, new Request(true)));
    }

    public static void anInitializedClassProceeds() {
        equal(new Transition<>(INITIALIZED, List.of(PROCEED)), ClassInitialization.decide(INITIALIZED, new Request(false)));
        equal(new Transition<>(INITIALIZED, List.of(PROCEED)), ClassInitialization.decide(INITIALIZED, new Request(true)));
    }

    public static void anErroneousClassThrowsOnEveryRequest() {
        equal(new Transition<>(ERRONEOUS, List.of(THROW_NO_CLASS_DEF_FOUND_ERROR)), ClassInitialization.decide(ERRONEOUS, new Request(false)));
    }

    public static void completionInitializesAndWakesTheWaiters() {
        equal(new Transition<>(INITIALIZED, List.of(NOTIFY_ALL)), ClassInitialization.decide(IN_PROGRESS, new Completed()));
    }

    public static void failureMarksTheClassErroneous() {
        equal(new Transition<>(ERRONEOUS, List.of(NOTIFY_ALL, RETHROW)), ClassInitialization.decide(IN_PROGRESS, new Failed(true)));
        equal(new Transition<>(ERRONEOUS, List.of(NOTIFY_ALL, WRAP_IN_EXCEPTION_IN_INITIALIZER_ERROR)),
                ClassInitialization.decide(IN_PROGRESS, new Failed(false)));
    }

    public static void anInitializerCannotEndWhenNoneRuns() {
        check(ClassInitialization.decide(UNINITIALIZED, new Completed()) instanceof Decision.Rejected, "completed");
        check(ClassInitialization.decide(INITIALIZED, new Failed(false)) instanceof Decision.Rejected, "failed");
    }
}
