package ob;

import java.util.TimeZone;

/** The default time zone's offset when the class was initialized: a setting the JDK reads, not the class path. */
public class Zoned {
    public static final int OFFSET = TimeZone.getDefault().getRawOffset() / 3600000;
}
