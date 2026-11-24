import java.util.Properties;

/** Run in a fresh single-threaded JVM. All observations use the same private key. */
public final class LiveProperties {
    private static final String KEY = "org.intheloop.recovery.privateKey";

    static final class Saved {
        static final String value = System.getProperty(KEY);
    }

    private static void check(String name, boolean answer) {
        if (!answer) throw new AssertionError(name);
        System.out.println(name);
    }

    public static void main(String[] args) {
        Properties parent = System.getProperties();
        check("same initial table", parent == System.getProperties());
        check("private key initially absent", !parent.containsKey(KEY) && parent.getProperty(KEY) == null);
        String first = new String("table value");
        String second = new String("table value");
        check("equal distinct strings", first != second && first.equals(second));
        System.setProperty(KEY, first);
        check("original table has installed reference", parent.get(KEY) == first);
        check("initializer saved installed reference", Saved.value == first);
        check("setter returns old reference", System.setProperty(KEY, second) == first);
        check("table has replacement reference", parent.getProperty(KEY) == second);
        check("saved reference survives replacement", Saved.value == first);
        Properties child = new Properties(parent);
        System.setProperties(child);
        check("replacement installed", System.getProperties() == child);
        check("child contains no own key", !child.containsKey(KEY));
        check("map get ignores defaults", child.get(KEY) == null);
        check("property lookup uses live defaults", child.getProperty(KEY) == second && System.getProperty(KEY) == second);
        check("parent removal returns replacement", parent.remove(KEY) == second);
        check("removal updates inherited lookup", child.getProperty(KEY) == null && System.getProperty(KEY) == null);
        check("saved reference survives removal", Saved.value == first);
    }
}
