package oc;

import java.util.Calendar;
import java.util.Date;
import java.util.TimeZone;

public final class CalendarAmounts {
    static final Calendar START = Calendar.getInstance();

    public static boolean canonical() {
        int[] years = {1600, 1900, 1969, 1970, 2000, 2012, 9999};
        int[] months = {1, 2, 11, 0, 1, 11, 11};
        int[] days = {29, 1, 31, 1, 29, 31, 31};
        long[] expected = {-11670994677000L, -2203887477000L, -82677000L, 3723000L,
                951786123000L, 1356915723000L, 253402218123000L};
        for (int i = 0; i < years.length; i++) {
            Calendar c = i % 2 == 0 ? Calendar.getInstance() : Calendar.getInstance(TimeZone.getTimeZone("UTC"));
            c.set(years[i], months[i], days[i], 1, 2, 3);
            c.set(Calendar.MILLISECOND, i);
            Date saved = c.getTime();
            c.set(1970, 0, 1, 0, 0, 0);
            c.set(Calendar.MILLISECOND, 0);
            if (saved == c.getTime() || saved.getTime() != expected[i] + i || c.getTimeInMillis() != 0L) return false;
        }
        return true;
    }

    public static long partial() {
        Calendar c = Calendar.getInstance();
        c.set(Calendar.MILLISECOND, 0);
        return c.getTimeInMillis();
    }

    public static void main(String[] args) { System.out.println(canonical()); }
}
