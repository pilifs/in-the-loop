import java.util.Arrays;
import java.util.List;

public final class ListHistory {
    static final class Cell { int value; }

    static boolean history(int value, boolean throughCollection) {
        Cell first = new Cell();
        Cell other = new Cell();
        Cell[] source = {first, other, first};
        List<Cell> list = throughCollection ? List.copyOf(Arrays.asList(source)) : List.of(source);
        source[0] = other;
        first.value = value;
        return list.size() == 3 && list.get(0) == first && list.get(1) == other
            && list.get(2) == first && list.get(0).value == value && other.value == 0;
    }

    public static boolean fromArray(int value) { return history(value, false); }
    public static boolean fromCollection(int value) { return history(value, true); }

    public static boolean followsSlot(int value) {
        Cell cell = new Cell();
        Cell[] source = {cell, cell};
        List<Cell> list = List.of(source);
        source[0] = new Cell();
        cell.value = value;
        return list.get(0) == source[0];
    }
}
