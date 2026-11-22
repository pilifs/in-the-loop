import java.io.BufferedOutputStream;
import java.io.DataOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.zip.GZIPOutputStream;
import springwork.BindingHistory;
import springwork.RoleApplication;
import static org.intheloop.controls.Grid.fields;
import static org.intheloop.controls.Grid.row;

/** Three real authorization decisions on a fresh binder and bean for each history. */
public final class GatedHistories {
    static final int HISTORY_COUNT = 2 * 2 * 6 * 16 * 16 * 16;

    record Input(boolean shared, int prefix, int[] order, int[] masks) {
        static Input at(int id) {
            if (id < 0 || id >= HISTORY_COUNT) throw new IllegalArgumentException("history id " + id);
            int[] masks = {(id >> 8) & 15, (id >> 4) & 15, id & 15};
            int group = id >> 12;
            return new Input(group >= 12, 16 * ((group / 6) % 2), BindingHistory.order(group % 6), masks);
        }
    }

    record Step(boolean granted, int edits, BindingHistory.Snapshot state) {
        Object[] observation() {
            return new Object[]{granted, edits, state.bean(), state.error()};
        }
    }

    static Step[] trace(Input input, boolean alwaysApplyFirst) {
        var session = new BindingHistory.Session(input.shared());
        var steps = new Step[3];
        for (int i = 0; i < steps.length; i++) {
            boolean granted = RoleApplication.decide(input.prefix() + input.masks()[i], true, false);
            if (granted || (alwaysApplyFirst && i == 0)) session.edit(input.order()[i]);
            steps[i] = new Step(granted, session.edits, session.sample());
        }
        return steps;
    }

    static Object[] observations(Step[] trace) {
        return Arrays.stream(trace).map(Step::observation).toArray();
    }

    static int index(Map<BindingHistory.Snapshot, Integer> states, BindingHistory.Snapshot state) {
        return states.computeIfAbsent(state, unused -> states.size());
    }

    public static void main(String[] args) throws Exception {
        if (args[0].equals("--case")) {
            int id = Integer.parseInt(args[1]);
            Input input = Input.at(id);
            row(id, fields("shared", input.shared(), "prefix", RoleApplication.prefix(input.prefix()),
                           "order", input.order(), "masks", input.masks()),
                observations(trace(input, false)), observations(trace(input, true)));
            return;
        }
        var states = new LinkedHashMap<BindingHistory.Snapshot, Integer>();
        try (var output = new DataOutputStream(new BufferedOutputStream(
                new GZIPOutputStream(Files.newOutputStream(Path.of(args[0])))))) {
            output.writeBytes("SGH1");
            for (boolean shared : new boolean[]{false, true}) {
                output.writeInt(index(states, new BindingHistory.Session(shared).sample()));
            }
            for (int id = 0; id < HISTORY_COUNT; id++) {
                Input input = Input.at(id);
                output.writeBoolean(input.shared());
                output.writeByte(input.prefix());
                for (int edit : input.order()) output.writeByte(edit);
                for (int mask : input.masks()) output.writeByte(mask);
                for (Step step : trace(input, false)) {
                    output.writeBoolean(step.granted());
                    output.writeInt(step.edits());
                    output.writeInt(index(states, step.state()));
                }
            }
        }
        LoadedClasses.main(Arrays.copyOfRange(args, 1, args.length));
        // Intern only observations. Every history above still built a new session and executed all three decisions.
        states.forEach((state, id) -> row(id, null, new Object[]{state.bean(), state.error()}, null));
    }
}
