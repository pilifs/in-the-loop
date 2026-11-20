package paint;

public final class Paint {
    public static Outcome run(int mask) {
        Outcome out = new Outcome();
        try {
            try (Layer l = new Layer("L", (mask & 1) != 0, out); Layer r = new Layer("R", (mask & 2) != 0, out)) { if ((mask & 4) != 0) throw new Tagged("B"); }
        } catch (Tagged primary) {
            out.primary = primary;
        }
        return out;
    }
}
