package org.intheloop.observation;

/** Observer-owned state for one single-threaded checked entry. */
public final class SiteState {
    public static int flags;
    public static void mark(int bit) { flags |= bit; }
    public static final class Raised {
        final Throwable exception;
        final Raised previous;
        Raised(Throwable exception, Raised previous) { this.exception = exception; this.previous = previous; }
    }
    public static Raised raised(Throwable exception, Raised previous) {
        mark(2);
        return new Raised(exception, previous);
    }
    public static void leaving(Throwable exception, Raised seen) {
        for (Raised p = seen; p != null; p = p.previous)
            if (p.exception == exception) { mark(32); return; }
    }
}
