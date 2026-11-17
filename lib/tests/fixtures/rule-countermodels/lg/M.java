package lg;

import java.util.logging.Level;
import java.util.logging.Logger;

/** Entry points that log one line at WARNING, and a main that prints what each returns on a JVM. */
public class M {
    /** How often the default handler asked the record for its message: 1 on a JVM. */
    public static int seen() {
        Logger log = Logger.getLogger("lg");
        Counted r = new Counted(Level.WARNING, "x");
        log.log(r);
        return r.seen;
    }

    /** Whether log returned: 0 on a JVM, whose handler lets the record's Throwable out. */
    public static int escaped() {
        Logger log = Logger.getLogger("lg");
        try {
            log.log(new Thrown(Level.WARNING, "x"));
            return 1;
        } catch (Throwable t) {
            return 0;
        }
    }

    public static void main(String[] args) {
        System.out.println("seen=" + seen() + " escaped=" + escaped());
    }
}
