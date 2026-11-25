/** Let the existing debugger qualify the original method reached by the measured public caller. */
public class UpgradeProbe {
    public static String observe(String[] args) throws Exception {
        return PublicCaller.observe(args);
    }
}
