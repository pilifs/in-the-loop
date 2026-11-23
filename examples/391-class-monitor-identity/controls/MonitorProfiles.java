/** One caller observation inside the lock. Run each entry in a fresh process. */
public final class MonitorProfiles {
    static int shared;
    static final class Explicit extends Thread {
        public void run() { synchronized (Explicit.class) { shared = 6; } }
    }
    static final class Implicit extends Thread {
        static synchronized void write() { shared = 6; }
        public void run() { write(); }
    }
    public static void matched() {
        Explicit worker = new Explicit();
        synchronized (Explicit.class) { shared = 5; worker.start(); assert shared == 5; }
    }
    public static void mixed() {
        Explicit worker = new Explicit();
        synchronized (worker) { shared = 5; worker.start(); assert shared == 5; }
    }
    public static void staticMethod() {
        Implicit worker = new Implicit();
        synchronized (Implicit.class) { shared = 5; worker.start(); assert shared == 5; }
    }
}
