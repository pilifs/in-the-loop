package seats;

import java.util.Arrays;

public final class Reservations {
    static final class Result {
        final int[][] acknowledgement = new int[2][2];
        final int[] owners = new int[2];
        final int[][] logs = new int[2][];
        final int[][] invoked = new int[2][2], returned = new int[2][2];
        int ticks;
        synchronized int event() { return ++ticks; }
    }

    static Result execute(int code) throws InterruptedException {
        int shape = code / 12;
        int order = code % 3;
        int[] calls = {1 + ((code / 6) % 2), 1 + ((code / 3) % 2)};
        Seat first = new Seat();
        Seat[] seat = {first, Handles.second(first, shape == 1)};
        Audit initial = new Audit();
        Audit[] log = {initial, shape == 2 ? initial : new Audit()};
        Result result = new Result();
        Thread[] workers = new Thread[2];
        for (int w = 0; w < 2; w++) {
            final int id = w;
            workers[w] = new Thread(() -> {
                for (int j = 0; j < calls[id]; j++) {
                    result.invoked[id][j] = result.event();
                    result.acknowledgement[id][j] = seat[id].reserve(id+1,log[id]) ? 1 : -1;
                    result.returned[id][j] = result.event();
                }
            });
        }
        int start = order == 1 ? 1 : 0;
        workers[start].start();
        if (order != 2) workers[start].join();
        workers[1-start].start();
        workers[0].join();
        workers[1].join();
        for (int id=0; id<2; id++) {
            result.owners[id] = seat[id].owner;
            result.logs[id] = Arrays.copyOf(log[id].events, log[id].used);
        }
        return result;
    }

    public static int singleOwner(int code) throws InterruptedException {
        Result r = execute(code);
        if (code / 12 == 1) return r.owners[0] == r.owners[1] ? 1 : 0;
        return r.owners[0] == 1 && r.owners[1] == 2 ? 1 : 0;
    }
}
