package net.terminalvalue.crosscut.ratelimit;

import static net.terminalvalue.crosscut.Tests.check;

public final class WindowTest {

    private WindowTest() {}

    private static final long WINDOW = 1_000_000_000L;

    public static void countsRequestsInTheSameWindow() {
        Window window = new Window(0, 0).counted(100, WINDOW).counted(200, WINDOW).counted(WINDOW - 1, WINDOW);
        check(window.startNanos() == 0, "the first window starts at the epoch");
        check(window.count() == 3, "three requests in the window");
    }

    public static void startsTheNextWindowAtOne() {
        Window window = new Window(0, 2).counted(WINDOW + 5, WINDOW);
        check(window.startNanos() == WINDOW, "the next window starts a window later");
        check(window.count() == 1, "the request that opened the window");
        window = window.counted(2 * WINDOW, WINDOW);
        check(window.startNanos() == 2 * WINDOW && window.count() == 1, "and the one after it");
    }

    public static void rejectsTimeGoingBackOrAnEmptyWindow() {
        boolean rejected = false;
        try {
            new Window(WINDOW, 1).counted(WINDOW - 1, WINDOW);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "a reading before the window's start");
        rejected = false;
        try {
            new Window(0, 0).counted(1, 0);
        } catch (IllegalArgumentException e) {
            rejected = true;
        }
        check(rejected, "a window of nothing");
    }
}
