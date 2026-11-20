package queuegrid;

public final class BoundedQueue {
    private final int[] values = new int[2];
    private int size;
    public int apply(int command) {
        if (command == 2) {
            if (size == 0) return 4;
            int first = values[0];
            values[0] = values[1];
            size--;
            return 2 + first;
        }
        if (size == 2) return 0;
        values[size++] = command;
        return 1;
    }
    public int size() { return size; }
    public int at(int i) { return values[i]; }
}
