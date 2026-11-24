/** Invoke the independently registered, byte-identical reference caller. */
public final class UpgradeProbe {
    public static String observe(String[] args) throws java.io.IOException {
        int input = Integer.parseInt(args[1]);
        if (args[0].equals("primary")) return Long.toString(ReferenceAPI.primary(input));
        if (args[0].equals("control")) return Long.toString(ReferenceAPI.control(input));
        throw new IllegalArgumentException("unregistered observer");
    }
}
