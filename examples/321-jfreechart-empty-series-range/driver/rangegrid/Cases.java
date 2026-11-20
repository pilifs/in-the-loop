package rangegrid;

import org.intheloop.controls.Grid;
import static org.intheloop.controls.Grid.fields;
import java.util.*;
import org.jfree.data.Range;
import org.jfree.data.time.*;

public final class Cases {
    public static void main(String[] args) {
        int code=0;
        for(Integer a:new Integer[]{null,-1,0,1}) for(Integer b:new Integer[]{null,-1,0,1}) {
            if(a==null&&b==null)continue;
            for(String order:new String[]{"AB","BA"}) {
                TimeSeries x=new TimeSeries("A"), y=new TimeSeries("B");
                if(a!=null)x.add(new Year(2012),a);
                if(b!=null)y.add(new Year(2012),b);
                TimeSeriesCollection c=new TimeSeriesCollection(TimeZone.getTimeZone("UTC"));
                c.addSeries(x);c.addSeries(y);
                Range r=c.getRangeBounds(Arrays.asList(order.substring(0,1),order.substring(1)),
                        new Range(1325376000000L,1356998399999L),false);
                Grid.row(code,fields("A",a,"B",b,"order",order,"year",2012,"zone","UTC","includeInterval",false),
                    fields("lower",r==null?null:Double.toString(r.getLowerBound()),"upper",r==null?null:Double.toString(r.getUpperBound())),
                    fields("lower",Projection.lower(code),"upper",Projection.upper(code)));
                code++;
            }
        }
    }
}
