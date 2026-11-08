package throttle;

/** A throttle of a fixed capacity: what calls have taken so far, never above the capacity. */
public class Throttle {
    private final int capacity;
    private int used;

    public Throttle(int capacity) {
        if (capacity < 1) {
            throw new IllegalArgumentException("capacity below 1");
        }
        this.capacity = capacity;
    }

    /** Takes n units, at most what is left. The setup call. */
    public void take(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("negative units");
        }
        used = n >= capacity - used ? capacity : used + n;
    }

    /** Whether n more units fit. The target. */
    public boolean allows(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("negative units");
        }
        return n <= capacity - used;
    }
}
