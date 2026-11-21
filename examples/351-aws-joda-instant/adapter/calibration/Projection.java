package calibration;

import com.amazonaws.util.DateUtils;
import java.util.Date;

public final class Projection {
    public static long roundtrip(boolean ordinary) throws Exception {
        long value = ordinary ? 946684800123L : Long.MAX_VALUE;
        return DateUtils.parseISO8601Date(DateUtils.formatISO8601Date(new Date(value))).getTime();
    }
}
