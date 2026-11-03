package net.terminalvalue.mica.init;

/** What happens to a class's initialization: a thread asks for it, or its initializer ends. */
public sealed interface InitEvent {

    /**
     * A thread needs the class initialized: {@code new}, {@code getstatic}, {@code putstatic}, {@code invokestatic},
     * reflection, or the initialization of a subclass (JVMS §5.5).
     *
     * @param byInitializingThread whether the requesting thread is the one recorded as running the class's
     *                             initializer, which makes the request recursive
     */
    record Request(boolean byInitializingThread) implements InitEvent {}

    /** The class's initialization method ({@code <clinit>}) completed normally. */
    record Completed() implements InitEvent {}

    /**
     * The class's initialization method completed abruptly by throwing.
     *
     * @param error whether the exception is an {@code Error} or one of its subclasses, which is rethrown as it
     *              is; anything else is wrapped in an {@code ExceptionInInitializerError}
     */
    record Failed(boolean error) implements InitEvent {}
}
