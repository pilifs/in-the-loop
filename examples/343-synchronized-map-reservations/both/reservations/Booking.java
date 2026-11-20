package reservations;

import java.util.concurrent.CyclicBarrier;
import java.util.concurrent.TimeUnit;

public final class Booking {
    static final class History {
        int tick, size;
        final int[] calls = new int[2], returns = new int[2];
        final boolean[] winners = new boolean[2];
        final String[] owners = new String[2];
        synchronized int event() { return ++tick; }
    }

    static History run(int code, boolean gated) throws Exception {
        int mode = code % 3;
        boolean distinct = code / 3 != 0;
        CyclicBarrier barrier = new CyclicBarrier(2);
        Slots table = gated && mode == 2 ? new Slots() {
            @Override protected void between() {
                try { barrier.await(5, TimeUnit.SECONDS); }
                catch (Exception e) { throw new AssertionError(e); }
            }
        } : new Slots();
        History h = new History();
        Thread[] workers = new Thread[2];
        for (int i = 0; i < 2; i++) {
            final int caller = i;
            workers[i] = new Thread(() -> {
                h.calls[caller] = h.event();
                h.winners[caller] = table.reserve(distinct && caller == 1 ? "second" : "first", caller == 0 ? "A" : "B");
                h.returns[caller] = h.event();
            }, i == 0 ? "A" : "B");
        }
        int first = mode == 1 ? 1 : 0;
        workers[first].start();
        if (mode != 2) workers[first].join();
        workers[1-first].start();
        workers[0].join();
        workers[1].join();
        if (h.returns[0] == 0 || h.returns[1] == 0) throw new AssertionError("unfinished calls");
        h.size = table.slots.size();
        h.owners[0] = table.slots.get("first");
        h.owners[1] = table.slots.get("second");
        return h;
    }

    public static int size(int code) throws Exception { return run(code, false).size; }
    public static int history(int code) throws Exception {
        History h = run(code, false);
        if (code >= 3) return h.size == 2 && h.winners[0] && h.winners[1] && "A".equals(h.owners[0])
                && "B".equals(h.owners[1]) ? 1 : 0;
        for (int i = 0; i < 2; i++) {
            if (h.returns[1-i] > h.calls[i] && h.winners[i] && !h.winners[1-i] && h.size == 1
                    && (i == 0 ? "A" : "B").equals(h.owners[0]) && h.owners[1] == null) return 1;
        }
        return 0;
    }
}
