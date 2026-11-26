import com.squareup.moshi.*;

import java.util.*;

public class PublicCaller {
    public record GenericRecord<T>(T value) {}

    public record Inner<T>(T single, List<T> list, Map<String, T> map) {}

    public record Longs(Inner<Long> value) {}

    public record Strings(Inner<String> value) {}

    static String typed(Object o) {
        return o.getClass().getSimpleName() + ":" + o;
    }

    static <T> String read(
            JsonAdapter<T> adapter, String json, java.util.function.Function<T, Inner<?>> unwrap)
            throws Exception {
        T v = adapter.fromJson(json);
        var inner = unwrap.apply(v);
        return typed(inner.single())
                + "/"
                + inner.list().stream().map(PublicCaller::typed).toList()
                + "/"
                + typed(inner.map().get("five"))
                + "/"
                + v.equals(adapter.fromJson(adapter.toJson(v)));
    }

    public static String observe(String[] a) throws Exception {
        var moshi = new Moshi.Builder().build();
        if (a[0].equals("control")) {
            var adapter =
                    moshi.<GenericRecord<String>>adapter(
                            Types.newParameterizedTypeWithOwner(
                                    PublicCaller.class, GenericRecord.class, String.class));
            return typed(adapter.fromJson("{\"value\":\"plain\"}").value());
        }
        String nums = "{\"value\":{\"single\":1,\"list\":[2,3,4],\"map\":{\"five\":5}}}",
                strings =
                        "{\"value\":{\"single\":\"x\",\"list\":[\"y\",\"z\"],\"map\":{\"five\":\"w\"}}}";
        String first = read(moshi.adapter(Longs.class), nums, Longs::value);
        return a[0].equals("intent")
                ? first
                : first
                        + " / "
                        + read(moshi.adapter(Strings.class), strings, Strings::value)
                        + " / "
                        + read(moshi.adapter(Longs.class), nums, Longs::value);
    }
}
