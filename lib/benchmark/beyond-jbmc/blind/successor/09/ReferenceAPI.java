import com.conversantmedia.util.concurrent.ConcurrentStack;

public final class ReferenceAPI {
    public static long primary(int n) {
        ConcurrentStack<Integer> s = new ConcurrentStack<>(8);
        if (n == 1) { s.push(42); s.pop(); }
        try { return s.peek() == null ? 0 : 1; }
        catch (IndexOutOfBoundsException ex) { return -1; }
    }
    public static long control(int n) {
        ConcurrentStack<Integer> s = new ConcurrentStack<>(8);
        s.push(42);
        int observed = s.peek();
        return s.size() == 1 && s.pop() == observed ? observed : -1;
    }
}
