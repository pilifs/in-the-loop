import com.fasterxml.jackson.annotation.*;

import tools.jackson.databind.annotation.JsonDeserialize;
import tools.jackson.databind.json.JsonMapper;

import java.util.*;

public class PublicCaller {
    @JsonDeserialize(builder = Builder.class)
    public record Value(int a, int b, int c, int d) {
        String fields() {
            return a + "," + b + "," + c + "," + d;
        }
    }

    @JsonPropertyOrder({"a", "b", "c", "d"})
    public static class Builder {
        final int a, b, c, d;

        @JsonCreator
        public Builder(@JsonProperty("c") int c) {
            this(0, 0, c, 0);
        }

        private Builder(int a, int b, int c, int d) {
            this.a = a;
            this.b = b;
            this.c = c;
            this.d = d;
        }

        public Builder withA(int v) {
            return new Builder(v, b, c, d);
        }

        public Builder withB(int v) {
            return new Builder(a, v, c, d);
        }

        public Builder withD(int v) {
            return new Builder(a, b, c, v);
        }

        public Value build() {
            return new Value(a, b, c, d);
        }
    }

    public static class Bean {
        final int id;
        String name;

        @JsonCreator
        public Bean(@JsonProperty("id") int id) {
            this.id = id;
        }

        public String setName(String s) {
            return name = s;
        }
    }

    public static String observe(String[] a) {
        var mapper = JsonMapper.builder().build();
        if (a[0].equals("control")) {
            var b = mapper.readValue("{\"name\":\"value\",\"id\":7}", Bean.class);
            return b.id + "/" + b.name;
        }
        if (a[0].equals("intent"))
            return mapper.readValue("{\"a\":5,\"b\":6,\"c\":7,\"d\":8}", Value.class).fields();
        var array =
                JsonMapper.builder()
                        .withConfigOverride(
                                Builder.class,
                                o -> o.setFormat(JsonFormat.Value.forShape(JsonFormat.Shape.ARRAY)))
                        .build();
        List<String> rows = new ArrayList<>();
        for (int b : new int[] {6, 16}) {
            rows.add(
                    mapper.readValue("{\"c\":7,\"a\":5,\"b\":" + b + ",\"d\":8}", Value.class)
                            .fields());
            rows.add(
                    mapper.readValue("{\"a\":5,\"b\":" + b + ",\"d\":8,\"c\":7}", Value.class)
                            .fields());
            rows.add(array.readValue("[5," + b + ",7,8]", Value.class).fields());
        }
        return String.join(" / ", rows);
    }
}
