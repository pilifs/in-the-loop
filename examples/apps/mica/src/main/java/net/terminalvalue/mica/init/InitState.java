package net.terminalvalue.mica.init;

/**
 * The initialization state of a class or interface, which its {@code Class} object indicates (JVMS §5.5): the
 * four states the initialization procedure distinguishes.
 */
public enum InitState {
    /** Verified and prepared, but not initialized. */
    UNINITIALIZED,
    /** Being initialized by some particular thread, which is recorded. */
    IN_PROGRESS,
    /** Fully initialized and ready for use. */
    INITIALIZED,
    /** Initialization failed; every later request throws {@code NoClassDefFoundError}. */
    ERRONEOUS
}
