import com.fasterxml.jackson.annotation.JsonMerge;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.json.JsonMapper;

import java.util.*;

public class PublicCaller {
    public enum Key {
        A,
        B,
        C
    }

    public static class Value {
        public String data;
        public int count;

        private Value(String d, int n) {
            data = d;
            count = n;
        }
    }

    public static class Bean {
        @JsonMerge public EnumMap<Key, Value> values = new EnumMap<>(Key.class);

        public Bean() {
            for (var k : Key.values()) values.put(k, new Value("init-" + k, 0));
        }
    }

    public static class Fresh {
        public String a;
    }

    static String update(String data, int count, boolean tree) {
        var mapper = JsonMapper.builder().build();
        var bean = new Bean();
        bean.values.put(Key.C, new Value(data, count));
        var alias = bean.values.get(Key.A);
        Bean r = mapper.readerForUpdating(bean).readValue("{\"values\":{\"A\":{\"count\":3}}}");
        if (!tree)
            return (r == bean)
                    + "/"
                    + (r.values.get(Key.A) == alias)
                    + "/"
                    + alias.count
                    + "/"
                    + alias.data
                    + "/"
                    + r.values.get(Key.C).data;
        var node =
                JsonMapper.builder().build().readTree(mapper.writeValueAsBytes(bean)).get("values");
        return node.get("A").get("count").asInt()
                + "/"
                + node.get("A").get("data").asString()
                + "/"
                + alias.count
                + "/"
                + node.get("C").get("data").asString()
                + "/"
                + node.get("C").get("count").asInt();
    }

    public static String observe(String[] a) {
        if (a[0].equals("challenge"))
            return update("first", 4, true) + " / " + update("second", 8, true);
        if (a[0].equals("intent")) return update("init-C", 0, false);
        EnumMap<Key, Fresh> r =
                JsonMapper.builder()
                        .build()
                        .readValue(
                                "{\"A\":{\"a\":\"x\"}}",
                                new TypeReference<EnumMap<Key, Fresh>>() {});
        return r.size() + "/" + r.get(Key.A).a;
    }
}
