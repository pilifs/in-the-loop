package lh;

import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/** Entry points that log one record at WARNING, and a main that prints what each returns on a JVM. */
public class M {
    /** Whether log returned: 0 on a JVM, whose handler lets the OutOfMemoryError out. */
    public static int huge() {
        return returned(new Huge(Level.WARNING, "x"));
    }

    /** Whether log returned: 0 on a JVM, whose handler lets the StackOverflowError out. */
    public static int deep() {
        return returned(new Deep(Level.WARNING, "x"));
    }

    private static int returned(LogRecord r) {
        Logger log = Logger.getLogger("lh");
        try {
            log.log(r);
            return 1;
        } catch (Throwable t) {
            return 0;
        }
    }

    public static void main(String[] args) {
        System.out.println("huge=" + huge() + " deep=" + deep());
    }
}
