import org.joda.time.DateTimeZone;

public final class ZoneChecks {
    static final long START=1672531200000L, END=1704067200000L;
    static final long DST=1680422400000L, STANDARD=1698562800000L;
    static final int HOUR=3600000;
    static final String MEXICO="America/Mexico_City", CONTROL="Etc/GMT+7";
    public static boolean oldSchedule(long instant) {
        return instant<START || instant>=END || DateTimeZone.forID(MEXICO).getOffset(instant)==(instant>=DST && instant<STANDARD?-5:-6)*HOUR;
    }
    public static boolean newSchedule(long instant) {
        return instant<START || instant>=END || DateTimeZone.forID(MEXICO).getOffset(instant)==-6*HOUR;
    }
    public static boolean unaffected(long instant) {
        return instant<START || instant>=END || DateTimeZone.forID(CONTROL).getOffset(instant)==-7*HOUR;
    }
    public static int offsetMexico(long t){return DateTimeZone.forID(MEXICO).getOffset(t);}
    public static int offsetControl(long t){return DateTimeZone.forID(CONTROL).getOffset(t);}
    public static void main(String[] args) {
        if(!DateTimeZone.getProvider().getClass().getName().equals("org.joda.time.tz.ZoneInfoProvider"))throw new AssertionError();
        for(String id:new String[]{MEXICO,CONTROL}){
            DateTimeZone zone=DateTimeZone.forID(id);
            long cursor=START;
            System.out.println(id+" at-start "+zone.getOffset(cursor));
            while(true){
                long next=zone.nextTransition(cursor);
                if(next==cursor || next>=END)break;
                if(next<cursor)throw new AssertionError();
                System.out.println(id+" transition "+next+" "+zone.getOffset(next-1)+" "+zone.getOffset(next));
                cursor=next;
            }
        }
    }
}
