package net.terminalvalue.mica.init;

import static net.terminalvalue.mica.Decision.rejected;
import static net.terminalvalue.mica.Decision.transition;
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

import net.terminalvalue.mica.Decision;
import net.terminalvalue.mica.init.InitEvent.Completed;
import net.terminalvalue.mica.init.InitEvent.Failed;
import net.terminalvalue.mica.init.InitEvent.Request;

/**
 * The class initialization procedure of JVMS §5.5, as the decision the runtime makes while it holds the
 * initialization lock LC of the class. The runtime takes LC, reads the state the {@code Class} object indicates,
 * calls {@link #decide}, applies the new state, releases LC and performs the effects. The steps of the
 * specification are named in the comments.
 */
public final class ClassInitialization {

    private ClassInitialization() {}

    public static Decision<InitState, InitEffect> decide(InitState state, InitEvent event) {
        return switch (event) {
            case Request request -> switch (state) {
                // Step 6: record the current thread as the initializer and run the initialization (steps 7 to 9).
                case UNINITIALIZED -> transition(IN_PROGRESS, RUN_INITIALIZER);
                case IN_PROGRESS -> request.byInitializingThread()
                        // Step 3: a recursive request by the initializing thread completes normally.
                        ? transition(IN_PROGRESS, PROCEED)
                        // Step 2: another thread is initializing; wait on LC, then repeat the procedure.
                        : transition(IN_PROGRESS, WAIT);
                // Step 4: already initialized.
                case INITIALIZED -> transition(INITIALIZED, PROCEED);
                // Step 5: initialization failed once; it is not retried.
                case ERRONEOUS -> transition(ERRONEOUS, THROW_NO_CLASS_DEF_FOUND_ERROR);
            };
            // Step 10: mark the class initialized and wake the threads waiting on LC.
            case Completed _ -> state == IN_PROGRESS
                    ? transition(INITIALIZED, NOTIFY_ALL)
                    : rejected("no initialization is in progress");
            // Steps 11 and 12: mark the class erroneous, wake the waiters, and throw: the Error itself, or an
            // ExceptionInInitializerError around anything else.
            case Failed failed -> state == IN_PROGRESS
                    ? transition(ERRONEOUS, NOTIFY_ALL, failed.error() ? RETHROW : WRAP_IN_EXCEPTION_IN_INITIALIZER_ERROR)
                    : rejected("no initialization is in progress");
        };
    }
}
