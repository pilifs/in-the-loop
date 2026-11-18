package lh;

import java.util.logging.Level;
import java.util.logging.LogRecord;

/** A record whose message asks for an array no JVM makes: an OutOfMemoryError, with no athrow in the class. */
public class Huge extends LogRecord {
    public Huge(Level level, String message) {
        super(level, message);
    }

    @Override
    public String getMessage() {
        long[] cells = new long[Integer.MAX_VALUE];
        return cells.length > 0 ? super.getMessage() : null;
    }
}
