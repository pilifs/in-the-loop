import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.joda.JodaModule;
import org.joda.time.Duration;

public final class ReferenceAPI {
    private static ObjectMapper mapper() { return new ObjectMapper().registerModule(new JodaModule()); }
    public static long primary(int n) throws Exception {
        try {
            Duration d = mapper().readValue(n == 0 ? "\"\"" : "\"    \"", Duration.class);
            return d == null ? 0 : 1;
        } catch (IllegalArgumentException | com.fasterxml.jackson.core.JsonProcessingException ex) {
            return -1;
        }
    }
    public static long control(int n) throws Exception {
        return mapper().readValue("1234", Duration.class).getMillis();
    }
}
