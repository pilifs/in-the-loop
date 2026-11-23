import java.util.function.Supplier;
import org.springframework.core.NamedThreadLocal;

public final class ThreadLocalHistory {
    static final class Cell {}
    static final class Factory implements Supplier<Cell> {
        int calls;
        public Cell get() { calls++; return new Cell(); }
    }
    static ThreadLocal<Cell> key(boolean spring, Factory factory) {
        if (spring) return NamedThreadLocal.withInitial("subject", factory);
        return new ThreadLocal<Cell>() { protected Cell initialValue() { return factory.get(); } };
    }
    static boolean history(boolean spring, int choice) {
        Factory x = new Factory(), y = new Factory();
        ThreadLocal<Cell> a = key(spring, x), b = key(spring, y);
        b.remove(); b.remove();
        Cell first = a.get(), other = b.get();
        if (first == null || other == null || first == other || a.get() != first || b.get() != other) return false;
        if (choice == 0) a.set(null);
        if (choice == 1) { a.remove(); Cell fresh = a.get(); if (fresh == null || fresh == first || fresh == other) return false; }
        if (choice == 2) a.set(other);
        if (choice == 3) { b.remove(); b.remove(); Cell fresh = b.get(); return fresh != null && fresh != other && a.get() == first && x.calls == 1 && y.calls == 2; }
        return (choice != 0 || a.get() == null) && (choice != 2 || a.get() == other)
            && b.get() == other && x.calls == (choice == 1 ? 2 : 1) && y.calls == 1;
    }
    public static boolean kernel(int choice) { return history(false, choice); }
    public static boolean spring(int choice) { return history(true, choice); }
    public static boolean nullInitializes(boolean spring) {
        Factory f = new Factory(); ThreadLocal<Cell> key = key(spring, f);
        key.set(null);
        return key.get() != null && f.calls == 1;
    }
}
