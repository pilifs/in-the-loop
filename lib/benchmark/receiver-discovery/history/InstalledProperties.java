import java.util.Properties;

/** Public property calls on explicitly installed standard tables, with independent local aliases. */
public final class InstalledProperties {
    static final String KEY = "org.intheloop.recovery.privateKey";

    static final class Saved {
        static final String value = System.getProperty(KEY);
    }

    public static boolean liveIdentity() {
        Properties first = new Properties();
        System.setProperties(first);
        Properties alias = System.getProperties();
        Properties second = new Properties(first);
        System.setProperties(second);
        return first == alias && System.getProperties() == second && alias != second;
    }

    public static boolean wrongIdentity() {
        return !liveIdentity();
    }

    public static boolean ownAndInherited() {
        Properties parent = new Properties();
        System.setProperties(parent);
        String first = new String("value");
        String next = new String("value");
        if (first == next || System.setProperty(KEY, first) != null || Saved.value != first) return false;
        if (System.setProperty(KEY, next) != first || parent.get(KEY) != next) return false;
        Properties child = new Properties(parent);
        System.setProperties(child);
        return !child.containsKey(KEY) && child.get(KEY) == null && child.getProperty(KEY) == next
                && System.getProperty(KEY) == next && parent.remove(KEY) == next
                && child.getProperty(KEY) == null && Saved.value == first;
    }

    public static boolean nonStringPrevious() {
        Properties table = new Properties();
        table.put(KEY, new Object());
        System.setProperties(table);
        try {
            System.setProperty(KEY, "new");
            return false;
        } catch (ClassCastException expected) {
            return table.get(KEY) == "new";
        }
    }

    public static boolean unknownTableEmpty() {
        return System.getProperties().isEmpty();
    }
}
