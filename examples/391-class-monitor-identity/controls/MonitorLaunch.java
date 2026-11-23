public final class MonitorLaunch {
    public static void main(String[] args) throws Exception {
        boolean held;
        switch (args[0]) {
            case "mixed": held = MonitorIdentity.mixed(); break;
            case "matched": held = MonitorIdentity.matched(); break;
            case "synchronizedMethod": held = MonitorIdentity.synchronizedMethod(); break;
            default: throw new IllegalArgumentException(args[0]);
        }
        System.out.println(held ? "protected" : "exposed");
    }
}
