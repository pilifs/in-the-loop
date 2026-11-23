import java.util.ArrayDeque;
import java.util.ConcurrentModificationException;
import java.util.Iterator;
import java.util.NoSuchElementException;
import org.apache.commons.collections4.iterators.FilterIterator;
import org.apache.commons.collections4.iterators.SingletonIterator;

public final class DequeRemoval {
    static ArrayDeque<Object> deque(Object a, Object b) {
        ArrayDeque<Object> result = new ArrayDeque<>();
        result.add(a); result.add(b);
        return result;
    }
    public static boolean history(boolean ownerRemoves) {
        Object a = new Object(), b = new Object();
        ArrayDeque<Object> d = deque(a, b);
        Iterator<Object> it = d.iterator();
        try { it.remove(); return false; } catch (IllegalStateException expected) {}
        if (it.next() != a) return false;
        if (ownerRemoves) {
            if (d.pollLast() != b) return false;
            try { it.next(); return false; } catch (ConcurrentModificationException expected) { return true; }
        }
        it.remove();
        try { it.remove(); return false; } catch (IllegalStateException expected) {}
        if (d.size() != 1 || d.peekFirst() != b || it.next() != b) return false;
        try { it.next(); return false; } catch (NoSuchElementException expected) { return true; }
    }
    public static boolean stillReturns() {
        Object a = new Object(), b = new Object();
        ArrayDeque<Object> d = deque(a, b);
        Iterator<Object> it = d.iterator();
        it.next(); d.pollLast();
        try { return it.next() == b; } catch (ConcurrentModificationException e) { return false; }
    }
    public static boolean singleton(boolean removable) {
        Object a = new Object();
        FilterIterator<Object> f = new FilterIterator<>(new SingletonIterator<>(a, removable), o -> true);
        if (!f.hasNext() || !f.hasNext()) return false;
        try { f.remove(); return false; } catch (IllegalStateException expected) {}
        if (f.next() != a) return false;
        try { f.remove(); return removable; } catch (UnsupportedOperationException e) { return !removable; }
    }
    public static boolean filtered(boolean prefetch) {
        Object a = new Object(), b = new Object();
        ArrayDeque<Object> d = deque(a, b);
        FilterIterator<Object> f = new FilterIterator<>(d.iterator(), o -> true);
        if (f.next() != a) return false;
        if (!prefetch) { f.remove(); return d.size() == 1 && d.peekFirst() == b; }
        if (!f.hasNext()) return false;
        try { f.remove(); return false; } catch (IllegalStateException expected) {}
        if (d.size() != 2 || d.peekFirst() != a || d.peekLast() != b || f.next() != b) return false;
        f.remove();
        return d.size() == 1 && d.peekFirst() == a;
    }
}
