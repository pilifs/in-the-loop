package net.terminalvalue.quorum;

import java.util.List;

/**
 * What a state machine decides on one event: move to a new state with effects for the caller to perform, stay
 * where it is, or refuse the event. The kernels return decisions and perform nothing themselves, which is what
 * makes them pure, verifiable, and runnable in a deterministic simulation.
 *
 * @param <S> the state type, an enum
 * @param <E> the effect type, an enum
 */
public sealed interface Decision<S extends Enum<S>, E extends Enum<E>> {

    /** Move to {@code next} and perform {@code effects}, in order, in the caller's transaction. */
    record Transition<S extends Enum<S>, E extends Enum<E>>(S next, List<E> effects) implements Decision<S, E> {
        public Transition {
            effects = List.copyOf(effects);
        }
    }

    /** The event changes nothing: a duplicate, a stale message, or one that this state does not care about. */
    record Unchanged<S extends Enum<S>, E extends Enum<E>>(String reason) implements Decision<S, E> {}

    /** The event is refused, and the sender should be told so. */
    record Rejected<S extends Enum<S>, E extends Enum<E>>(String reason) implements Decision<S, E> {}

    @SafeVarargs
    static <S extends Enum<S>, E extends Enum<E>> Decision<S, E> transition(S next, E... effects) {
        return new Transition<>(next, List.of(effects));
    }

    static <S extends Enum<S>, E extends Enum<E>> Decision<S, E> unchanged(String reason) {
        return new Unchanged<>(reason);
    }

    static <S extends Enum<S>, E extends Enum<E>> Decision<S, E> rejected(String reason) {
        return new Rejected<>(reason);
    }
}
