import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParser;
import com.google.gson.JsonSyntaxException;
import com.google.gson.TypeAdapter;
import com.google.gson.reflect.TypeToken;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonWriter;

public final class UpgradeProbe {
    static final class ValueAdapter extends TypeAdapter<String> {
        final List<String> events = new ArrayList<>();
        IllegalStateException failure;

        @Override public void write(JsonWriter out, String value) throws IOException { out.value(value); }

        @Override public String read(JsonReader reader) throws IOException {
            events.add(reader.getPath());
            try {
                String value = reader.nextString();
                events.add(reader.getPreviousPath());
                return value;
            } catch (IllegalStateException original) {
                failure = original;
                String firstLine = original.getMessage().split("\n", 2)[0];
                int index = firstLine.lastIndexOf(" path ");
                if (index < 0 || !firstLine.contains("but was BEGIN_ARRAY")) throw new AssertionError(firstLine);
                events.add("error=" + firstLine.substring(index + 6));
                throw original;
            }
        }
    }

    public static String observe(String[] args) {
        ValueAdapter adapter = new ValueAdapter();
        Gson gson = new GsonBuilder().registerTypeAdapter(String.class, adapter).create();
        TypeToken<Map<Integer, String>> type = new TypeToken<Map<Integer, String>>() {};
        String good = "{\"1\":\"x\",\"2\":\"y\"}";
        String[] docs = args[1].equals("mixed")
                ? new String[]{good, "{\"01\":\"a\",\"002\":[]}", "{\"002\":\"z\",\"01\":\"r\"}"}
                : new String[]{good};
        List<String> result = new ArrayList<>();
        for (String doc : docs) {
            adapter.events.clear();
            adapter.failure = null;
            String outcome;
            try {
                Map<Integer, String> map = args[0].equals("stream")
                        ? gson.fromJson(doc, type) : gson.fromJson(JsonParser.parseString(doc), type);
                List<String> pairs = new ArrayList<>();
                for (Map.Entry<Integer, String> pair : map.entrySet())
                    pairs.add(pair.getKey().intValue() + "=" + pair.getValue());
                outcome = String.join(",", pairs);
            } catch (JsonSyntaxException e) {
                if (adapter.failure == null || e.getCause() != adapter.failure) throw e;
                StackTraceElement first = adapter.failure.getStackTrace()[0];
                outcome = "JsonSyntaxException/IllegalStateException@" + first.getClassName() + "." + first.getMethodName();
            }
            if (args[2].equals("paths")) outcome += "|" + String.join(",", adapter.events);
            result.add(outcome);
        }
        return String.join(";", result);
    }

    public static boolean readPaths() {
        return observe(new String[]{"stream", "mixed", "paths"}).startsWith("1=x,2=y");
    }
}
