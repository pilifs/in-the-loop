import java.util.TimeZone;

/** Public readbacks for the initial profile, installation, copy isolation and restoration. */
public final class ProcessZone {
    public static int offset() { return TimeZone.getDefault().getRawOffset(); }

    public static boolean isolateAndRestore() {
        TimeZone original = TimeZone.getDefault();
        TimeZone other = TimeZone.getDefault();
        int initial = original.getRawOffset();
        if (original == other) return false;
        other.setRawOffset(12345);
        if (TimeZone.getDefault().getRawOffset() != initial) return false;
        try {
            TimeZone supplied = TimeZone.getTimeZone("GMT-10:00");
            TimeZone.setDefault(supplied);
            supplied.setRawOffset(67890);
            TimeZone first = TimeZone.getDefault(), second = TimeZone.getDefault();
            if (first == second || first == supplied || first.getRawOffset() != -36000000) return false;
            first.setRawOffset(777);
            if (second.getRawOffset() != -36000000 || offset() != -36000000) return false;
        } finally {
            TimeZone.setDefault(original);
        }
        return offset() == initial;
    }

    public static boolean replaceBeforeRead() {
        TimeZone.setDefault(TimeZone.getTimeZone("GMT+10:00"));
        return offset() == 36000000;
    }

    public static int resetToHost() {
        TimeZone.setDefault(null);
        return offset();
    }

    public static void main(String[] args) {
        System.out.println(TimeZone.getDefault().getID() + " " + offset() + " " + isolateAndRestore() + " " + offset());
    }
}
