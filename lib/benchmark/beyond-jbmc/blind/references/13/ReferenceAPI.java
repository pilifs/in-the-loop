import java.util.*;
import io.opencensus.common.Timestamp;
import io.opencensus.metrics.LabelValue;
import io.opencensus.metrics.export.*;
public final class ReferenceAPI {
    static List<LabelValue> labels(){return Arrays.asList(LabelValue.create("first"),LabelValue.create("second"));}
    public static long primary(int n) {
        List<LabelValue> keys=labels();
        TimeSeries base=TimeSeries.create(keys);
        Point p=Point.create(Value.longValue(n),Timestamp.create(1,0)),q=Point.create(Value.longValue((long)n+1),Timestamp.create(2,0));
        TimeSeries a=base.setPoint(p),b=a.setPoint(q);
        return base.getPoints().isEmpty() && a.getPoints().equals(Collections.singletonList(p)) && b.getPoints().equals(Collections.singletonList(q))
            && a.getLabelValues().equals(keys) && b.getLabelValues().equals(keys)?1:0;
    }
    public static long control(int n){List<LabelValue> l=labels();TimeSeries b=TimeSeries.create(l);return b.getLabelValues().equals(l) && b.getStartTimestamp()==null?1:0;}
}
