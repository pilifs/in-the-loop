package net.terminalvalue.crosscut.idempotency;

import static net.terminalvalue.crosscut.Decision.rejected;
import static net.terminalvalue.crosscut.Decision.transition;
import static net.terminalvalue.crosscut.Decision.unchanged;
import static net.terminalvalue.crosscut.idempotency.KeyState.ABSENT;
import static net.terminalvalue.crosscut.idempotency.KeyState.COMPLETED;
import static net.terminalvalue.crosscut.idempotency.KeyState.IN_PROGRESS;
import static net.terminalvalue.crosscut.idempotency.ReceiverEffect.EXECUTE;
import static net.terminalvalue.crosscut.idempotency.ReceiverEffect.RELEASE_KEY;
import static net.terminalvalue.crosscut.idempotency.ReceiverEffect.REPLAY_RESPONSE;
import static net.terminalvalue.crosscut.idempotency.ReceiverEffect.STORE_RESPONSE;

import net.terminalvalue.crosscut.Decision;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Completed;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Expired;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Failed;
import net.terminalvalue.crosscut.idempotency.ReceiverEvent.Request;

/**
 * The decision rule of an idempotent receiver, the server side of an {@code Idempotency-Key} header: a request with
 * a key the server has not seen executes; a retry of a completed request gets the stored response; a retry of a
 * request still in progress is refused (409), because executing it again would do the work twice; a key reused with
 * a different request is refused (422). An attempt that dies without a response releases the key, so that the
 * client's retry can run.
 *
 * <p>The filter that owns the receiver looks the key up and applies the decision in one transaction, so that two
 * retries arriving together cannot both see ABSENT.
 */
public final class IdempotentReceiver {

    private IdempotentReceiver() {}

    public static Decision<KeyState, ReceiverEffect> decide(KeyState state, ReceiverEvent event) {
        return switch (event) {
            case Request request -> switch (state) {
                case ABSENT -> transition(IN_PROGRESS, EXECUTE);
                case IN_PROGRESS -> request.sameFingerprint()
                        ? rejected("a request with this key is in progress")
                        : rejected("the key was reused for a different request");
                case COMPLETED -> request.sameFingerprint()
                        ? transition(COMPLETED, REPLAY_RESPONSE)
                        : rejected("the key was reused for a different request");
            };
            case Completed _ -> switch (state) {
                case IN_PROGRESS -> transition(COMPLETED, STORE_RESPONSE);
                case ABSENT, COMPLETED -> unchanged("no attempt is in progress");
            };
            case Failed _ -> switch (state) {
                case IN_PROGRESS -> transition(ABSENT, RELEASE_KEY);
                case ABSENT, COMPLETED -> unchanged("no attempt is in progress");
            };
            case Expired _ -> switch (state) {
                case COMPLETED -> transition(ABSENT, RELEASE_KEY);
                case ABSENT -> unchanged("nothing to expire");
                case IN_PROGRESS -> unchanged("a key in progress does not expire");
            };
        };
    }
}
