package jodagrid;

import org.joda.time.*;
import org.joda.time.chrono.ISOChronology;

public final class Projection {
    static MonthDay date(int i) {
        return new MonthDay(i<3?2:3,i<3?27+i:i-2,ISOChronology.getInstanceUTC());
    }
    private static int read(int a,int b) { return Days.daysBetween(date(a),date(b)).getDays(); }
    public static int normal(int code) {
        try { read(code/5,code%5);return 1; } catch(IllegalArgumentException e){return 0;}
    }
    public static int days(int code) {
        try { return read(code/5,code%5)==code%5-code/5?1:0; } catch(IllegalArgumentException e){return 0;}
    }
    public static int reversal(int code) {
        try { return read(code/5,code%5)==-read(code%5,code/5)?1:0; } catch(IllegalArgumentException excluded){return 1;}
    }
}
