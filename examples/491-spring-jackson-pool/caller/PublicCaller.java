import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.reactivestreams.Publisher;
import reactor.core.publisher.*;
import tools.jackson.core.json.JsonFactory;
import tools.jackson.core.util.*;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.core.ResolvableType;
import org.springframework.core.io.buffer.*;
import org.springframework.http.MediaType;
import org.springframework.http.codec.json.JacksonJsonEncoder;

public class PublicCaller {
    public record Item(String text) {}
    static class Pool implements RecyclerPool<BufferRecycler> {
        int acquired, released;
        final RecyclerPool<BufferRecycler> delegate = JsonRecyclerPools.newConcurrentDequePool();
        public BufferRecycler acquirePooled() { acquired++; return delegate.acquirePooled(); }
        public void releasePooled(BufferRecycler r) { released++; delegate.releasePooled(r); }
    }
    static String drain(JacksonJsonEncoder encoder, Publisher<Item> input, MediaType type) {
        var element = ResolvableType.forClass(Item.class);
        if (!encoder.canEncode(element,type)) throw new IllegalStateException("not selected");
        var bytes = new ByteArrayOutputStream();
        encoder.encode(input,DefaultDataBufferFactory.sharedInstance,element,type,Map.of()).doOnNext(b -> {
            try { byte[] part = new byte[b.readableByteCount()]; b.read(part); bytes.writeBytes(part); }
            finally { DataBufferUtils.release(b); }
        }).blockLast();
        return bytes.toString(StandardCharsets.UTF_8);
    }
    public static String observe(String[] args) {
        var pool = new Pool();
        var encoder = new JacksonJsonEncoder(JsonMapper.builder(JsonFactory.builder().recyclerPool(pool).build()).build());
        var reader = JsonMapper.builder().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).build();
        if (args[0].equals("mono")) {
            var tree = reader.readTree(drain(encoder,Mono.just(new Item("one")),MediaType.APPLICATION_JSON));
            return "acquired=" + (pool.acquired>0) + " balanced=" + (pool.acquired==pool.released) + " object=" + tree.get("text").asString();
        }
        if (args[0].equals("array")) {
            var tree = reader.readValue(drain(encoder,Flux.just(new Item("one"),new Item("two")),MediaType.APPLICATION_JSON),Item[].class);
            return "array=" + Arrays.stream(tree).map(Item::text).toList();
        }
        var items = List.of(new Item("a\"b"),new Item("a\nb"));
        var runs = new ArrayList<String>();
        for (int n=0;n<2;n++) {
            var wire = drain(encoder,Flux.fromIterable(items),MediaType.APPLICATION_NDJSON);
            var decoded = wire.lines().filter(s -> !s.isEmpty()).map(s -> reader.readValue(s,Item.class)).toList();
            runs.add("records=" + decoded.size() + " equal=" + items.equals(decoded) + " balanced=" + (pool.acquired==pool.released));
        }
        return String.join(" / ",runs);
    }
}
