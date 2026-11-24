import org.joda.time.DateTimeZone;

public final class ZoneResourceEquality {
    public static int mexico(long instant) {return DateTimeZone.forID("America/Mexico_City").getOffset(instant);}
    public static int control(long instant) {return DateTimeZone.forID("Etc/GMT+7").getOffset(instant);}
    static boolean inYear(long instant) {return instant>=1672531200000L && instant<1704067200000L;}
    public static int boundedMexico(long instant) {return inYear(instant)?mexico(instant):0;}
    public static int boundedControl(long instant) {return inYear(instant)?control(instant):0;}
}
