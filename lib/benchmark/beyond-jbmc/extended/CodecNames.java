import org.apache.commons.codec.digest.MurmurHash3.IncrementalHash32;

public final class CodecNames {
    public static String name(boolean array) {
        return array ? IncrementalHash32[][].class.getName() : new IncrementalHash32().getClass().getName();
    }

    public static String hierarchy(boolean parent) {
        Class<?> type = new IncrementalHash32().getClass();
        return (parent ? type.getSuperclass() : type).getName();
    }

    public static String lookup(boolean x86) {
        String name = x86 ? "org.apache.commons.codec.digest.MurmurHash3$IncrementalHash32x86"
                          : "org.apache.commons.codec.digest.MurmurHash3$IncrementalHash32";
        try {
            return Class.forName(name).getName();
        } catch (ClassNotFoundException missing) {
            return "absent";
        }
    }
}
