package queuegrid;

public final class Projection {
    private static final int[] HISTORY = {0, 2, 2, 5, 14, 14, 17, 14, 14, 17, 20, 26, 35, 50, 50, 89, 50, 50, 89, 92, 98, 107, 50, 50, 89, 50, 50, 89, 92, 98, 107, 122, 158, 125, 122, 158, 161, 200, 206, 215, 266, 266, 305, 266, 266, 305, 524, 530, 539, 266, 266, 305, 266, 266, 305, 524, 530, 539, 554, 590, 557, 554, 590, 593, 632, 638, 647, 266, 266, 305, 266, 266, 305, 524, 530, 539, 266, 266, 305, 266, 266, 305, 524, 530, 539, 554, 590, 557, 554, 590, 593, 632, 638, 647, 698, 914, 737, 698, 914, 953, 740, 746, 755, 698, 914, 737, 698, 914, 953, 956, 962, 971, 770, 806, 1205, 986, 1022, 1241, 1280, 1286, 1295};
    private static final int[] CONTENTS = {0, 1, 2, 0, 4, 5, 1, 7, 8, 2, 0, 0, 0, 4, 5, 4, 7, 8, 5, 1, 1, 1, 4, 5, 7, 7, 8, 8, 2, 2, 2, 1, 1, 0, 2, 2, 0, 0, 0, 0, 4, 5, 4, 7, 8, 5, 4, 4, 4, 4, 5, 7, 7, 8, 8, 5, 5, 5, 4, 4, 1, 5, 5, 1, 1, 1, 1, 4, 5, 4, 7, 8, 5, 7, 7, 7, 4, 5, 7, 7, 8, 8, 8, 8, 8, 7, 7, 2, 8, 8, 2, 2, 2, 2, 1, 1, 1, 2, 2, 1, 0, 0, 0, 1, 1, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
    private static int check(int code, boolean history) {
        BoundedQueue queue = new BoundedQueue();
        int n = code, value = 0, place = 1;
        while (n != 0) {
            n--;
            value += place * (queue.apply(n % 3) + 1);
            place *= 6;
            n /= 3;
        }
        if (history) return value == HISTORY[code] ? 1 : 0;
        value = 0;
        place = 1;
        for (int i = 0; i < queue.size(); i++) {
            value += place * (queue.at(i) + 1);
            place *= 3;
        }
        return value == CONTENTS[code] ? 1 : 0;
    }
    public static int history(int code) { return check(code,true); }
    public static int contents(int code) { return check(code,false); }
}
