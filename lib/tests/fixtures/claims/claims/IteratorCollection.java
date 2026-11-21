package claims;

import java.util.*;
import java.util.function.Consumer;
import java.util.function.IntConsumer;
import java.util.stream.*;

public final class IteratorCollection {
    enum Size { SMALL {}, LARGE }

    enum Bad {
        ONLY;
        Bad() { if (fails()) throw new IllegalArgumentException(); }
        static boolean fails() { return true; }
    }

    public static boolean erroneous() {
        try { new EnumMap<Bad, String>(Bad.class); return false; }
        catch (ExceptionInInitializerError first) {
            try { EnumSet.noneOf(Bad.class); return false; }
            catch (NoClassDefFoundError next) { return true; }
        }
    }

    public static boolean enums() {
        Size[] copy = Size.values();
        copy[0] = Size.LARGE;
        Map<Size, String> map = new EnumMap<>(Size.class);
        map.put(Size.LARGE, "b"); map.putIfAbsent(Size.SMALL, "a");
        Set<Size> set = EnumSet.of(Size.SMALL, Size.LARGE);
        return "a".equals(map.putIfAbsent(Size.SMALL, "no")) && "b".equals(map.get(Size.LARGE))
                && set.contains(Size.SMALL) && set.remove(Size.LARGE) && !set.contains(Size.LARGE);
    }

    static final class Feed implements Iterator<String> {
        int calls;
        public boolean hasNext() { return false; }
        public String next() { throw new NoSuchElementException(); }
        @Override public void forEachRemaining(Consumer<? super String> consumer) {
            calls++;
            consumer.accept("a"); consumer.accept(null); consumer.accept("a");
        }
    }

    public static boolean collected() {
        String[] values = {"old", null, "z"};
        Stream<String> arrayStream = Stream.of(values).map(value -> value == null ? "empty" : value);
        values[0] = "new";
        List<String> taken = arrayStream.collect(Collectors.toList());
        if (taken.size() != 3 || !"new".equals(taken.get(0)) || !"empty".equals(taken.get(1)) || !"z".equals(taken.get(2))) return false;
        try { arrayStream.collect(Collectors.toList()); return false; } catch (IllegalStateException expected) { }
        Feed it = new Feed();
        Spliterator<String> source = Spliterators.spliteratorUnknownSize(it, Spliterator.ORDERED);
        Stream<String> stream = StreamSupport.stream(source, false);
        if (it.calls != 0) return false;
        List<String> list = stream.collect(Collectors.toList());
        if (it.calls != 1 || list.size() != 3 || !"a".equals(list.get(0)) || list.get(1) != null || list.get(2) != list.get(0)) return false;
        try { stream.collect(Collectors.toList()); return false; } catch (IllegalStateException expected) { return it.calls == 1; }
    }

    static final class Visit {
        int count;
        long append(int n) { count++; if (n < 0) throw new IllegalArgumentException(); return 0x100000000L; }
        long any(Object value) { count++; return 1L; }
        Visit() { }
        Visit(int[] cell) { cell[0]++; }
    }

    public static boolean discard(boolean throwsFirst) {
        Visit state = new Visit();
        IntConsumer accept = state::append;
        try { accept.accept(throwsFirst ? -1 : 1); if (throwsFirst) return false; }
        catch (IllegalArgumentException expected) { if (!throwsFirst) return false; }
        accept.accept(0);
        int[] cell = {0};
        Consumer<int[]> allocate = Visit::new;
        allocate.accept(cell);
        return state.count == 2 && cell[0] == 1;
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    public static boolean erased() {
        java.util.function.IntUnaryOperator marked =
                (java.util.function.IntUnaryOperator & java.io.Serializable) (n -> n + 1);
        java.util.function.IntUnaryOperator plain = n -> n + 1;
        if (!(marked instanceof java.io.Serializable) || plain instanceof java.io.Serializable
                || marked.applyAsInt(4) != 5 || plain.applyAsInt(4) != 5) return false;
        Visit state = new Visit();
        Consumer<String> typed = state::any;
        try { ((Consumer) typed).accept(Integer.valueOf(1)); return false; }
        catch (ClassCastException expected) { if (state.count != 0) return false; }
        typed.accept(null);
        return state.count == 1;
    }

    public static boolean reset(boolean truncate) {
        StringBuilder b = new StringBuilder("xy");
        b.setLength(truncate ? 0 : 1);
        b.setLength(3);
        if (b.charAt(0) != (truncate ? 0 : 'x') || b.charAt(1) != 0 || b.charAt(2) != 0) return false;
        ArrayList<String> l = new ArrayList<>(); l.add("old"); l.clear(); l.add("new");
        return l.size() == 1 && "new".equals(l.get(0));
    }

    public static boolean wrong() {
        Feed it = new Feed();
        List<String> values = StreamSupport.stream(Spliterators.spliteratorUnknownSize(it, 0), false).collect(Collectors.toList());
        return values.isEmpty();
    }

    public static boolean stackFrames(boolean pushNull) {
        Stack<Object> stack = new Stack<>();
        Object root = new Object();
        Object leaf = pushNull ? null : new Object();
        List<Object> view = Collections.unmodifiableList(stack);
        if (stack.push(root) != root || stack.push(leaf) != leaf || stack.peek() != leaf
                || view.get(0) != root || view.size() != 2) return false;
        if (stack.pop() != leaf || stack.pop() != root || !view.isEmpty()) return false;
        try { stack.peek(); return false; } catch (EmptyStackException expected) { }
        try { stack.pop(); return false; } catch (EmptyStackException expected) { }
        Iterator<Object> only = Collections.singletonList(root).iterator();
        if (!only.hasNext() || only.next() != root || only.hasNext()) return false;
        try { only.next(); return false; } catch (NoSuchElementException expected) { }
        try { view.add(root); return false; } catch (UnsupportedOperationException expected) { return true; }
    }

    public static void main(String[] args) { if (!enums() || !erroneous() || !erased() || !collected() || !discard(false) || !discard(true) || !reset(true) || !reset(false) || !stackFrames(false) || !stackFrames(true) || wrong()) throw new AssertionError(); }
}
