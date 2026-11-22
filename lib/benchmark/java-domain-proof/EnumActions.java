package campaign;

import java.util.Arrays;
import org.apache.avro.Resolver;
import org.apache.avro.Schema;

public final class EnumActions {
    static Resolver.Action resolve(int code, String name) {
        boolean reverse = (code & 2) != 0;
        Schema writer = Schema.createEnum("E", null, "writer", Arrays.asList("A", "B"));
        Schema reader = Schema.createEnum(name, null, "reader",
                reverse ? Arrays.asList("B", "A") : Arrays.asList("A", "B"));
        return Resolver.resolve(writer, reader);
    }

    public static int renamed(int code) {
        Resolver.Action action = resolve(code, "E");
        if (!(action instanceof Resolver.EnumAdjust)) return 0;
        Resolver.EnumAdjust adjusted = (Resolver.EnumAdjust) action;
        int ordinal = code & 1;
        int destination = (code & 2) != 0 ? 1 - ordinal : ordinal;
        return adjusted.adjustments[ordinal] == destination
                && (ordinal == 0 ? "A" : "B").equals(adjusted.values[ordinal].toString()) ? 1 : 0;
    }

    public static int rejected(int code) {
        Resolver.Action action = resolve(code, "Other");
        return action instanceof Resolver.ErrorAction &&
                ((Resolver.ErrorAction) action).error == Resolver.ErrorAction.ErrorType.NAMES_DONT_MATCH ? 1 : 0;
    }

    public static void main(String[] args) {
        boolean fixed = "fix".equals(args[0]);
        for (int code = 0; code < 4; code++) {
            if (renamed(code) != (fixed ? 1 : 0) || rejected(code) != 1)
                throw new AssertionError("enum action " + code);
        }
    }
}
