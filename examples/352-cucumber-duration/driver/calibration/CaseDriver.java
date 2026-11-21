package calibration;

import com.fasterxml.jackson.databind.ObjectMapper;
import net.masterthought.cucumber.json.Result;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class CaseDriver {
    private static String direct(int code) throws Exception {
        long seconds = new int[]{0, 1, 59}[code / 6];
        long millis = new int[]{0, 1, 999}[(code / 2) % 3];
        long duration = seconds * 1000000000L + millis * 1000000L + new int[]{0, 999999}[code % 2];
        Result result = new ObjectMapper().readValue("{\"duration\":" + duration + "}", Result.class);
        return result.getFormattedDuration();
    }

    private static String encoded(String value) {
        return Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8));
    }

    public static void main(String[] args) throws Exception {
        for (int code = 0; code < 18; code++) {
            String actual = encoded(direct(code));
            String projected = encoded(Projection.format(code));
            System.out.println("{\"code\":" + code + ",\"direct\":\"" + actual
                    + "\",\"adapter\":\"" + projected + "\"}");
        }
    }
}
