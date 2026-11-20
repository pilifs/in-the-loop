package calibration;

import com.fasterxml.jackson.databind.ObjectMapper;
import net.masterthought.cucumber.json.Result;

public final class Projection {
    public static String format(int code) throws Exception {
        long seconds = code < 6 ? 0 : code < 12 ? 1 : 59;
        int index = (code / 2) % 3;
        long milliseconds = index == 0 ? 0 : index == 1 ? 1 : 999;
        long nanos = (seconds * 1000L + milliseconds) * 1000000L + (code % 2) * 999999L;
        Result result = new ObjectMapper().readValue("{\"duration\":" + nanos + "}", Result.class);
        return result.getFormattedDuration();
    }
}
