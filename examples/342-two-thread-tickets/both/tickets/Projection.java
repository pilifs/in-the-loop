package tickets;

import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.TimeUnit;

public final class Projection {
    static final class History {
        final int[] calls = new int[2], returns = new int[2], values = new int[2];
        int tick, state;
        synchronized int event() { return ++tick; }
    }

    static History history(int mode, boolean gate) throws Exception {
        CyclicBarrier bothRead = new CyclicBarrier(2);
        Counter counter = gate && mode == 2 ? new Counter() {
            @Override protected void between() {
                try { bothRead.await(5, TimeUnit.SECONDS); }
                catch (Exception ex) { throw new AssertionError(ex); }
            }
        } : new Counter();
        History history = new History();
        Thread[] workers = new Thread[2];
        for (int id = 0; id < 2; id++) {
            final int caller = id;
            workers[id] = new Thread(() -> {
                history.calls[caller] = history.event();
                history.values[caller] = counter.take();
                history.returns[caller] = history.event();
            }, id == 0 ? "A" : "B");
        }
        int first = mode == 1 ? 1 : 0;
        workers[first].start();
        if (mode != 2) workers[first].join();
        workers[1 - first].start();
        workers[0].join();
        workers[1].join();
        if (history.returns[0] == 0 || history.returns[1] == 0) throw new AssertionError("unfinished calls");
        history.state = counter.issued();
        return history;
    }

    public static int linearizable(int code) throws Exception {
        History h = history(code, false);
        boolean ab = h.returns[1] > h.calls[0] && h.values[0] == 1 && h.values[1] == 2;
        boolean ba = h.returns[0] > h.calls[1] && h.values[1] == 1 && h.values[0] == 2;
        return h.state == 2 && (ab || ba) ? 1 : 0;
    }
}
