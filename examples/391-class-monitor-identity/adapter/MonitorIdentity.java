public final class MonitorIdentity {
    static int shared;
    static class Worker extends Thread {
        boolean staticMethod;
        static synchronized void write() { shared = 6; }
        public void run() {
            if (staticMethod) write();
            else synchronized (Worker.class) { shared = 6; }
        }
    }
    static boolean observe(boolean differentLock, boolean staticMethod) throws InterruptedException {
        Worker w = new Worker();
        w.staticMethod = staticMethod;
        boolean protectedRead;
        synchronized (differentLock ? w : Worker.class) {
            shared = 5;
            w.start();
            protectedRead = shared == 5;
        }
        w.join();
        return protectedRead && shared == 6;
    }
    public static boolean matched() throws InterruptedException { return observe(false, false); }
    public static boolean mixed() throws InterruptedException { return observe(true, false); }
    public static boolean synchronizedMethod() throws InterruptedException { return observe(false, true); }

    // A concrete worker-first schedule of mixed(): the class monitor is free while the caller holds w.
    public static boolean workerFirst() throws InterruptedException {
        java.util.concurrent.CountDownLatch wrote = new java.util.concurrent.CountDownLatch(1);
        Worker w = new Worker() {
            public void run() { super.run(); wrote.countDown(); }
        };
        synchronized (w) {
            shared = 5;
            w.start();
            wrote.await();
            return shared == 5;
        }
    }
}
