import java.text.ParsePosition;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Standalone JDK reference. No Commons Lang classes are available to this program. */
public final class WeekReference {
    private static String instant(Calendar source, boolean lenient) {
        Calendar copy = (Calendar) source.clone();
        copy.setLenient(lenient);
        try { return String.valueOf(copy.getTimeInMillis()); }
        catch (IllegalArgumentException invalidFields) { return "invalid"; }
    }

    private static int calendarDay(int iso) {
        return iso == 7 ? Calendar.SUNDAY : iso + 1;
    }

    public static void main(String[] args) {
        boolean repaired = args[0].equals("new");
        Locale locale = args[1].equals("US") ? Locale.US : Locale.GERMANY;
        boolean lenient = args[2].equals("lenient");
        String[] days = args[3].equals("mixed") ? new String[]{"0", "7", "8", "15", "7"} : new String[]{"7", "x", "1", "7"};
        String source = "2025-W01-" + String.join("|2025-W01-", days);
        TimeZone zone = TimeZone.getTimeZone("UTC");
        Calendar fields = Calendar.getInstance(zone, locale);
        fields.clear();
        fields.setLenient(lenient);
        SimpleDateFormat jdk = new SimpleDateFormat("YYYY-'W'ww-u", locale);
        jdk.setTimeZone(zone);
        jdk.setLenient(lenient);
        int start = 0, lastError = -1;
        for (String text : days) {
            fields.set(Calendar.YEAR, 2025);
            fields.set(Calendar.WEEK_OF_YEAR, 1);
            int index = start + 9;
            String status;
            if (text.equals("x")) {
                status = "false";
                lastError = index;
            } else {
                int iso = Integer.parseInt(text);
                int day = repaired && (iso < 1 || iso > 7) ? iso : calendarDay(iso);
                fields.set(Calendar.DAY_OF_WEEK, day);
                int week = 1;
                if (repaired && lenient && (iso < 1 || iso > 7)) {
                    week += Math.floorDiv(iso - 1, 7);
                    day = calendarDay(Math.floorMod(iso - 1, 7) + 1);
                }
                index += text.length();
                try {
                    fields.setWeekDate(2025, week, day);
                    status = "true";
                } catch (IllegalArgumentException invalid) { status = invalid.getClass().getName(); }
            }
            ParsePosition referenceCursor = new ParsePosition(start);
            Date parsed = jdk.parse(source, referenceCursor);
            String jdkInstant = parsed == null ? "rejected" : Long.toString(parsed.getTime());
            String originalMode = instant(fields, lenient);
            if (repaired && ((parsed != null) != status.equals("true")
                    || (parsed != null && (!jdkInstant.equals(originalMode) || referenceCursor.getIndex() != index)))) {
                throw new AssertionError("calendar specification and SimpleDateFormat differ at " + text + ": " + status + "/" + jdkInstant);
            }
            int mask = 0;
            for (int i = 0; i < Calendar.FIELD_COUNT; i++) if (fields.isSet(i)) mask |= 1 << i;
            System.out.println(String.join(",", text, status, String.valueOf(index), String.valueOf(lastError),
                    String.valueOf(mask), originalMode, instant(fields, true)) + "\t" + jdkInstant
                    + "\t" + referenceCursor.getIndex() + "\t" + referenceCursor.getErrorIndex());
            start += 10 + text.length();
        }
    }
}
