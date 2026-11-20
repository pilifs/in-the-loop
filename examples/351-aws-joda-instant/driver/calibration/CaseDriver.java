package calibration;

import com.amazonaws.util.DateUtils;
import java.util.Date;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class CaseDriver {
    private static String direct(int code) throws Exception {
        long[] instants = {Long.MAX_VALUE, 946684800123L};
        String printed = DateUtils.formatISO8601Date(new Date(instants[code]));
        return Long.toString(DateUtils.parseISO8601Date(printed).getTime());
    }

    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 2; code++) {
            String actual = encoded(direct(code));
            String projected = encoded(Long.toString(Projection.roundtrip(code != 0)));
            System.out.println("{\"code\":" + code + ",\"direct\":\"" + actual
                    + "\",\"adapter\":\"" + projected + "\"}");
        }
    }
}
