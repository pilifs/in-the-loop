import java.util.ArrayList;
import java.util.Arrays;
import tools.jackson.core.JsonToken;
import tools.jackson.databind.MappingIterator;
import tools.jackson.dataformat.csv.CsvMapper;
import tools.jackson.dataformat.csv.CsvReadFeature;

/** Resolve the row boundary independently of the historical caller's iterator configuration. */
public class JacksonWrapping {
    public static String observe(String[] args) throws Exception {
        String csv = "\"te,st\"\n\"x\"\"y\"";
        var mapper = CsvMapper.builder().build();
        if (args[0].equals("tokens")) {
            var tokens = new ArrayList<String>();
            try (var parser = mapper.createParser(csv)) {
                for (JsonToken t; (t = parser.nextToken()) != null;) {
                    tokens.add(t == JsonToken.VALUE_STRING ? t + "(" + parser.getString() + ")" : t.name());
                }
            }
            return tokens.toString();
        }
        var result = new ArrayList<String>();
        try (MappingIterator<String[]> it = mapper.readerFor(String[].class)
                .with(CsvReadFeature.WRAP_AS_ARRAY).readValues(csv)) {
            for (int row = 0; row < 2; row++) {
                boolean first = it.hasNextValue();
                boolean second = it.hasNextValue();
                if (!first || !second) return result + " early end " + first + "," + second;
                String[] values = it.nextValue();
                result.add(first + "," + second + " width=" + values.length + " " + Arrays.toString(values));
            }
            return result + " eof=" + it.hasNextValue() + "," + it.hasNext();
        }
    }
}
