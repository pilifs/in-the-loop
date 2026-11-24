import java.text.ParsePosition;
import java.util.Calendar;
import java.util.Locale;
import java.util.TimeZone;
import org.apache.commons.lang3.time.FastDateFormat;

public final class UpgradeProbe {
    private static String millis(Calendar cal) {
        try { return Long.toString(cal.getTimeInMillis()); }
        catch (IllegalArgumentException invalidFields) { return "invalid"; }
    }

    // Reading a Calendar can complete and normalize its fields. Inspect copies before the next parse.
    private static String snapshot(Calendar actual) {
        int set = 0;
        for (int field = 0; field < Calendar.FIELD_COUNT; field++) {
            if (actual.isSet(field)) set |= 1 << field;
        }
        Calendar atMode = (Calendar) actual.clone();
        Calendar normalized = (Calendar) actual.clone();
        normalized.setLenient(true);
        return set + "," + millis(atMode) + "," + millis(normalized);
    }

    public static String observe(String[] args) {
        TimeZone utc = TimeZone.getTimeZone("UTC");
        Locale locale = args[0].equals("US") ? Locale.US : Locale.GERMANY;
        FastDateFormat format = FastDateFormat.getInstance("YYYY-'W'ww-u", utc, locale);
        Calendar target = Calendar.getInstance(utc, locale);
        target.clear();
        target.setLenient(args[1].equals("lenient"));
        ParsePosition cursor = new ParsePosition(0);
        String[] days = args[2].equals("mixed") ? new String[]{"0", "7", "8", "15", "7"} : new String[]{"7", "x", "1", "7"};
        String source = "2025-W01-" + String.join("|2025-W01-", days);
        StringBuilder result = new StringBuilder();
        int start = 0;
        for (String day : days) {
            cursor.setIndex(start);
            String status;
            try { status = Boolean.toString(format.parse(source, cursor, target)); }
            catch (IllegalArgumentException invalidDay) { status = invalidDay.getClass().getName(); }
            if (result.length() > 0) result.append("/");
            result.append(day).append(",").append(status).append(",").append(cursor.getIndex())
                  .append(",").append(cursor.getErrorIndex()).append(",").append(snapshot(target));
            start += 10 + day.length();
        }
        return result.toString();
    }

    public static boolean parseWeek() {
        return observe(new String[]{"US", "lenient", "mixed"}).contains("1736121600000");
    }
}
