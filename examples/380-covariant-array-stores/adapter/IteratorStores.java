import org.apache.commons.collections4.iterators.ObjectArrayListIterator;

public final class IteratorStores {
    public static boolean history(boolean integerArray, boolean advance, int kind) {
        Integer old = Integer.valueOf(1000);
        Number[] values = integerArray ? new Integer[]{old} : new Number[]{old};
        Number replacement = kind == 0 ? (Number) Integer.valueOf(7)
                : kind == 1 ? null : (Number) Double.valueOf(2.5);
        ObjectArrayListIterator<Number> iterator = new ObjectArrayListIterator<>(values);
        if (advance && iterator.next() != old) return false;
        int outcome;
        try { iterator.set(replacement); outcome = 0; }
        catch (IllegalStateException e) { outcome = 1; }
        catch (ArrayStoreException e) { outcome = 2; }
        int wanted = !advance ? 1 : integerArray && kind == 2 ? 2 : 0;
        return outcome == wanted && values[0] == (wanted == 0 ? replacement : old);
    }
}
