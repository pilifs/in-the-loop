import org.apache.commons.collections4.queue.CircularFifoQueue;
import org.apache.commons.lang3.ArrayFill;

public final class QueueFill {
    private static boolean history(int script, boolean checkFull) {
        if (script < 0 || script > 255) return true;
        CircularFifoQueue<Object> queue = new CircularFifoQueue<>(2);
        Object a = new Object(), b = new Object(), head = null, tail = null;
        int count = 0;
        for (int i = 0; i < 4; i++) {
            int op = (script >>> (2 * i)) & 3;
            if (op < 2) {
                Object item = op == 0 ? a : b;
                if (!queue.offer(item)) return false;
                if (count == 2) head = tail;
                if (count == 0) head = item; else tail = item;
                if (count < 2) count++;
            } else if (op == 2) {
                if (queue.poll() != head) return false;
                if (count > 0) count--;
                head = tail;
                tail = null;
            } else {
                queue.clear();
                head = tail = null;
                count = 0;
            }
            if (queue.size() != count || queue.peek() != head || queue.isAtFullCapacity() != (count == 2))
                return false;
            if (count > 0 && queue.get(0) != head || count > 1 && queue.get(1) != tail) return false;
            if (checkFull && queue.isFull() != (count == 2)) return false;
        }
        return true;
    }

    public static boolean queue(int script) { return history(script, false); }
    public static boolean fullMeansOccupied(int script) { return history(script, true); }

    static final class Cell { int value; }
    public static boolean fill(int value) {
        Cell stale = new Cell(), replacement = new Cell();
        Cell[] cells = {stale, stale};
        Cell[] returned = ArrayFill.fill(cells, replacement);
        replacement.value = value;
        return returned == cells && cells[0] == replacement && cells[1] == replacement
            && cells[0].value == value && cells[1].value == value;
    }

    public static boolean staleSurvives(int value) {
        Cell stale = new Cell(), replacement = new Cell();
        stale.value = value;
        Cell[] cells = {stale, stale};
        ArrayFill.fill(cells, replacement);
        return cells[1] == stale;
    }

    public static boolean covariant(boolean empty) {
        Integer original = Integer.valueOf(1);
        Object[] cells = empty ? new Integer[0] : new Integer[]{original};
        try {
            return ArrayFill.fill(cells, "x") == cells && empty;
        } catch (ArrayStoreException expected) {
            return !empty && cells[0] == original;
        }
    }
}
