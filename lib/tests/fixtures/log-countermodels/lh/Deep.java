package lh;

import java.util.logging.Level;
import java.util.logging.LogRecord;

/** A record whose message recurses without end: a StackOverflowError, with no athrow in the class. */
public class Deep extends LogRecord {
    public Deep(Level level, String message) {
        super(level, message);
    }

    @Override
    public String getMessage() {
        return depth(0);
    }

    private String depth(int k) {
        return depth(k + 1);
    }
}
