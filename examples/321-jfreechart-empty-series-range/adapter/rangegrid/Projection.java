package rangegrid;

import java.util.Arrays;
import java.util.TimeZone;
import org.jfree.data.Range;
import org.jfree.data.time.*;

public final class Projection {
    public static boolean populated(int code) {
        int pair=1+code/2;
        return pair/4!=0 && pair%4!=0;
    }
    private static int check(int code, boolean lower) {
        int pair=1+code/2, a=pair/4, b=pair%4;
        TimeSeries x=new TimeSeries("A"), y=new TimeSeries("B");
        if(a!=0)x.add(new Year(2012),a-2);
        if(b!=0)y.add(new Year(2012),b-2);
        TimeSeriesCollection series=new TimeSeriesCollection(TimeZone.getTimeZone("UTC"));
        series.addSeries(x);series.addSeries(y);
        Range range=series.getRangeBounds(code%2==0?Arrays.asList("A","B"):Arrays.asList("B","A"),
            new Range(1325376000000L,1356998399999L),false);
        int expected=a==0?b-2:b==0?a-2:lower?Math.min(a,b)-2:Math.max(a,b)-2;
        return range!=null && (lower?range.getLowerBound():range.getUpperBound())==expected?1:0;
    }
    public static int lower(int code){return check(code,true);}
    public static int upper(int code){return check(code,false);}
}
