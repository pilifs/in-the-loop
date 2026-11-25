import java.util.Arrays;
import tools.jackson.databind.MappingIterator;
import tools.jackson.dataformat.csv.*;

public class PublicCaller {
    public static class Person { public int age; public String name; }

    public static String observe(String[] args) throws Exception {
        var mapper = CsvMapper.builder().build();
        if (args[0].equals("bean")) {
            var schema = CsvSchema.builder().addColumn("age").addColumn("name").build();
            try (MappingIterator<Person> it = mapper.readerFor(Person.class).with(schema).readValues("13,\"Joe\"")) {
                var p = it.nextValue();
                return p.age + " " + p.name + "; eof=" + it.hasNextValue();
            }
        }
        boolean two = args[0].equals("two");
        String text = "\"te,st\"" + (two ? "\n\"x\"\"y\"" : "");
        try (MappingIterator<String[]> it = mapper.readerFor(String[].class)
                .without(CsvReadFeature.WRAP_AS_ARRAY).readValues(text)) {
            var output = new StringBuilder();
            for (int i = 0; i < (two ? 2 : 1); i++) {
                if (i > 0) output.append("; ");
                boolean ready = it.hasNextValue();
                output.append(ready);
                if (two) output.append(",").append(it.hasNextValue());
                if (!ready) return output + "; eof=" + it.hasNextValue() + "," + it.hasNext();
                String[] row;
                try { row = it.nextValue(); }
                catch (tools.jackson.databind.exc.MismatchedInputException e) {
                    return output + " " + e.getClass().getSimpleName();
                }
                // The comma in the first value is caller data, so verify the array cardinality separately.
                output.append(" ").append(row.length == 1 ? Arrays.toString(row) : "width=" + row.length + Arrays.toString(row));
            }
            return output + "; eof=" + it.hasNextValue() + "," + it.hasNext();
        }
    }
}
