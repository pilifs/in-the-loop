import edu.uci.ics.jung.visualization.picking.MultiPickedState;
import java.util.Set;

public final class ReferenceAPI {
    public static long primary(int n) {
        MultiPickedState<String> picked = new MultiPickedState<>();
        Set<String> view = picked.getPicked();
        int[] events = {0};
        picked.addItemListener(e -> events[0]++);
        if (picked.pick("v", true) || !picked.pick("v", true)) return -1;
        if (n == 1 && !picked.pick("v", false)) return -2;
        return events[0] * 10 + view.size();
    }
    public static long control(int n) {
        MultiPickedState<String> a = new MultiPickedState<>(), b = new MultiPickedState<>();
        a.pick("v", true);
        return !b.isPicked("v") && b.getPicked().isEmpty() ? 1 : 0;
    }
}
