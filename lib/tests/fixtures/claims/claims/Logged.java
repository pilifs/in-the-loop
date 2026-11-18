package claims;

import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

/**
 * A line logged at WARNING, as Spring's logging adapter logs it (example 287's encoder warns of a stored hash that
 * is empty or not bcrypt's), and what would make logging observable: a level, a filter or a handler set on a logger,
 * and a record that writes elsewhere when it is formatted. Each method returns true on a JVM under the JDK's default
 * logging configuration, except the countermodels, which return false there (or throw) where a model that took
 * logging for granted would say true: the own checker proves the first kind and stops at the second.
 */
public final class Logged {
    private Logged() {}

    /** Under the default configuration a logger logs INFO, WARNING and SEVERE. */
    public static boolean loud(int k) {
        Logger logger = Logger.getLogger("claims.Logged");
        return logger.isLoggable(Level.INFO) && logger.isLoggable(Level.WARNING) && logger.isLoggable(Level.SEVERE);
    }

    /** OFF is the JDK's call. */
    public static boolean off(int k) {
        return Logger.getLogger("claims.Logged").isLoggable(Level.OFF) || k == k;
    }

    /** A record that finds its caller in a stack trace and keeps it, as Spring's LocationResolvingLogRecord does. */
    static final class Located extends LogRecord {
        private static final String SELF = Located.class.getName();
        private volatile boolean resolved;

        Located(Level level, String message) {
            super(level, message);
        }

        @Override
        public String getSourceClassName() {
            if (!resolved) resolve();
            return super.getSourceClassName();
        }

        @Override
        public void setSourceClassName(String name) {
            super.setSourceClassName(name);
            resolved = true;
        }

        private void resolve() {
            StackTraceElement[] stack = new Throwable().getStackTrace();
            String found = null;
            for (StackTraceElement e : stack) {
                if (!SELF.equals(e.getClassName())) {
                    found = e.getClassName();
                    break;
                }
            }
            setSourceClassName(found);
        }
    }

    /** A line logged at WARNING the way Spring's JavaUtilLog logs one returns normally. */
    public static boolean warned(int k) {
        Logger logger = Logger.getLogger("claims.Logged");
        if (logger.isLoggable(Level.WARNING)) {
            Object message = "warned";
            LogRecord record = new Located(Level.WARNING, String.valueOf(message));
            record.setLoggerName("claims.Logged");
            record.setResourceBundleName(logger.getResourceBundleName());
            record.setResourceBundle(logger.getResourceBundle());
            record.setThrown(null);
            logger.log(record);
        }
        return true;
    }

    /** A record needs a level, and a logger a record. */
    public static boolean nulls(int k) {
        boolean level = false;
        boolean record = false;
        try {
            new LogRecord(null, "nulls");
        } catch (NullPointerException e) {
            level = true;
        }
        try {
            Logger.getLogger("claims.Logged").log((LogRecord) null);
        } catch (NullPointerException e) {
            record = true;
        }
        return level && record && "null".equals(String.valueOf((Object) null));
    }

    static int described;

    /** Countermodel: String.valueOf of another object calls its toString, which counts; false on a JVM. */
    public static boolean described(int k) {
        described = 0;
        Object message = new Object() {
            @Override
            public String toString() {
                described++;
                return "described";
            }
        };
        String.valueOf(message);
        return described == 0;
    }

    static int formatted;

    /** A record that counts how often it is formatted. */
    static final class Counted extends LogRecord {
        Counted(Level level, String message) {
            super(level, message);
        }

        @Override
        public String getMessage() {
            formatted++;
            return super.getMessage();
        }
    }

    /** Countermodel: the default handler formats the record, which counts, so on a JVM this is false. */
    public static boolean counted(int k) {
        formatted = 0;
        Logger.getLogger("claims.Logged").log(new Counted(Level.WARNING, "counted"));
        return formatted == 0;
    }

    /** Countermodel: a logger given a level logs less; false on a JVM. */
    public static boolean levelled(int k) {
        Logger logger = Logger.getLogger("claims.Logged.levelled");
        logger.setLevel(Level.SEVERE);
        return logger.isLoggable(Level.WARNING);
    }

    /** Countermodel: a filter's exception leaves Logger.log; on a JVM this throws. */
    public static boolean filtered(int k) {
        Logger logger = Logger.getLogger("claims.Logged.filtered");
        logger.setFilter(r -> {
            throw new IllegalStateException("filtered");
        });
        logger.log(new LogRecord(Level.WARNING, "filtered"));
        return true;
    }

    /** Countermodel: so does a handler's; on a JVM this throws. */
    public static boolean handled(int k) {
        Logger logger = Logger.getLogger("claims.Logged.handled");
        logger.addHandler(new Handler() {
            @Override
            public void publish(LogRecord record) {
                throw new IllegalStateException("handled");
            }

            @Override
            public void flush() {}

            @Override
            public void close() {}
        });
        logger.log(new LogRecord(Level.WARNING, "handled"));
        return true;
    }
}
