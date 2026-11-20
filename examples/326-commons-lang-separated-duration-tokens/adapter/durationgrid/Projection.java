package durationgrid;

import org.apache.commons.lang3.time.DurationFormatUtils;

public final class Projection {
    private static String format(int h,String pattern,boolean pad) {
        return DurationFormatUtils.formatDuration(h*3600000L,pattern,pad);
    }
    private static String hour(int h) {
        return new String[]{"0","1","2","3","4","5","6","7","8","9","10","11","12"}[h];
    }
    public static int text(int code) {
        int h=code/6, p=code%3; boolean pad=(code/3)%2!=0;
        String field=hour(h);
        String want=p==2?(pad&&h<10?"0"+field:field):field+"x"+field;
        return want.equals(format(h,p==0?"HxH":p==1?"H'x'H":"HH",pad))?1:0;
    }
    public static int quoting(int code) {
        int h=code/6;boolean pad=(code/3)%2!=0;
        return format(h,"HxH",pad).equals(format(h,"H'x'H",pad))?1:0;
    }
}
