package lg;

import java.util.logging.Level;
import java.util.logging.LogRecord;

/** A record whose message throws a checked Throwable, which a handler's catch of Exception does not catch. */
public class Thrown extends LogRecord {
    public Thrown(Level level, String message) {
        super(level, message);
    }

    @Override
    public String getMessage() {
        Thrown.<RuntimeException>sneak(new Throwable("formatted"));
        return super.getMessage();
    }

    @SuppressWarnings("unchecked")
    static <T extends Throwable> void sneak(Throwable t) throws T {
        throw (T) t;
    }
}
