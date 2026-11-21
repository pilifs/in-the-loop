import com.fasterxml.jackson.databind.InjectableValues;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.File;
import net.masterthought.cucumber.Configuration;
import net.masterthought.cucumber.json.Result;

public final class OriginalFixture {
    public static void main(String[] args) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        Configuration configuration = new Configuration(new File("."), "upstream fixture observation");
        mapper.setInjectableValues(new InjectableValues.Std().addValue(Configuration.class, configuration));
        JsonNode feature = mapper.readTree(new File(args[0])).get(0);
        if (!"1st feature".equals(feature.path("name").asText())) {
            throw new IllegalStateException("Unexpected first feature in the historical fixture");
        }
        JsonNode step = feature.get("elements").get(0).get("steps").get(2);
        Result result = mapper.treeToValue(step.get("result"), Result.class);
        System.out.println(result.getDuration() + "\t" + result.getFormattedDuration());
    }
}
