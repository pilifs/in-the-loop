package net.terminalvalue.mica;

import java.util.List;

/**
 * What a state machine of the virtual machine decides on one event: move to a new state with effects for the
 * caller to perform, stay where it is, or refuse the event. The kernels return decisions and perform nothing
 * themselves: the runtime that owns the kernel (the class loader with its lock, the interpreter) performs the
 * effects, and the kernel stays a function that can be proved and put into a model.
 *
 * @param <S> the state type, an enum
 * @param <E> the effect type, an enum
 */
public sealed interface Decision<S extends Enum<S>, E extends Enum<E>> {

    /** Move to {@code next} and perform {@code effects}, in order. {@code next} may be the current state. */
    record Transition<S extends Enum<S>, E extends Enum<E>>(S next, List<E> effects) implements Decision<S, E> {
        public Transition {
            effects = List.copyOf(effects);
        }
    }

    /** The event changes nothing and needs no effect. */
    record Unchanged<S extends Enum<S>, E extends Enum<E>>(String reason) implements Decision<S, E> {}

    /** The event is refused: it cannot happen in this state, and the runtime that raised it has a bug. */
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
