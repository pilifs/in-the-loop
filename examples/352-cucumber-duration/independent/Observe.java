import com.fasterxml.jackson.databind.ObjectMapper;
import net.masterthought.cucumber.json.Result;

public final class Observe {
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        for (long seconds : new long[]{0, 1, 59}) {
            for (long millis : new long[]{0, 1, 999}) {
                for (long remainder : new long[]{0, 999999}) {
                    long nanos = seconds * 1000000000L + millis * 1000000L + remainder;
                    Result result = mapper.readValue("{\"duration\":" + nanos + "}", Result.class);
                    System.out.println(nanos + "\t" + result.getDuration() + "\t" + result.getFormattedDuration());
                }
            }
        }
    }
}
