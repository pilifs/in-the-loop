package lg;

import java.util.logging.Level;
import java.util.logging.LogRecord;

/** A record that counts how often its message is asked for: in its own field, which its caller can read. */
public class Counted extends LogRecord {
    public int seen;

    public Counted(Level level, String message) {
        super(level, message);
    }

    @Override
    public String getMessage() {
        seen++;
        return super.getMessage();
    }
}
