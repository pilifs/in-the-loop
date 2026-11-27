import java.util.Properties;

/** Controlled startup histories for distinguishing an actual table, a live view and inherited defaults. */
public class TableControls {
    private static String mode;
    private static Properties retained;
    static final class Custom extends Properties {}
    public static int sample() {
        Properties table = System.getProperties();
        if (mode.equals("named")) return System.getProperty("startup.fixture.selected", "missing").length();
        if (mode.equals("view")) return table.keySet().size();
        if (mode.equals("save")) retained = table;
        if (mode.equals("replace")) System.setProperties(new Properties());
        if (mode.equals("mutate")) table.setProperty("startup.fixture.changed", "now");
        return table.hashCode();
    }
    public static void main(String[] args) throws Exception {
        mode = args[0];
        if (mode.equals("defaults")) {
            Properties defaults = new Properties();
            defaults.setProperty("startup.fixture.inherited", "_");
            Properties replacement = new Properties(defaults);
            replacement.putAll(System.getProperties());
            System.setProperties(replacement);
        } else if (mode.equals("custom")) {
            Custom replacement = new Custom();
            replacement.putAll(System.getProperties());
            System.setProperties(replacement);
        } else if (mode.equals("nonstring")) System.getProperties().put(42, "not a string key");
        System.out.println("hash=" + sample());
        if (mode.equals("plain")) System.out.println(ObservedInitializer.tableSnapshot(System.getProperties()));
    }
    public static class Startup {
        static final boolean PRESENT;
        static {
            boolean[] found = {false};
            System.getProperties().forEach((key, value) -> {
                if (key.equals("startup.fixture.selected") && value.equals("present")) found[0] = true;
            });
            PRESENT = found[0];
        }
        public static boolean present() { return PRESENT; }
    }
    public static class Failing {
        static final int COUNT;
        static {
            int hash = System.getProperties().hashCode();
            if (System.getProperty("startup.fixture.fail") != null) throw new IllegalArgumentException("controlled startup failure");
            COUNT = hash;
        }
        public static int count() { return COUNT; }
    }
}
