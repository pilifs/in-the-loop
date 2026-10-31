package net.terminalvalue.mica.init;

/** What the runtime does with the initialization lock LC released, as the procedure of JVMS §5.5 directs. */
public enum InitEffect {
    /** Record the current thread as the initializer and run the superclass initializations and {@code <clinit>}. */
    RUN_INITIALIZER,
    /** Block on LC until notified, then request again. */
    WAIT,
    /** Complete normally: the class can be used. */
    PROCEED,
    /** Throw {@code NoClassDefFoundError}. */
    THROW_NO_CLASS_DEF_FOUND_ERROR,
    /** Wake every thread waiting on LC. */
    NOTIFY_ALL,
    /** Rethrow the initializer's exception as it is. */
    RETHROW,
    /** Wrap the initializer's exception in an {@code ExceptionInInitializerError} and throw that. */
    WRAP_IN_EXCEPTION_IN_INITIALIZER_ERROR
}
