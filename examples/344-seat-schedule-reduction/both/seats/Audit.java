package seats;

public final class Audit {
    final int[] events = new int[6];
    int used;
    public synchronized void append(int acknowledgement) {
        events[used] = acknowledgement;
        used++;
    }
}
