import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;
import org.bson.Document;
import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.MongoIterable;
import org.springframework.boot.mongodb.health.MongoHealthIndicator;
import org.springframework.boot.mongodb.health.MongoReactiveHealthIndicator;
import org.springframework.boot.health.contributor.Health;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import static org.mockito.Mockito.*;

public class PublicCaller {
    static Document hello(Object command, String name, List<String> calls) {
        if (!new Document("hello", 1).equals(command)) throw new IllegalArgumentException("unexpected command");
        calls.add(name);
        return new Document("maxWireVersion", 10);
    }
    @SuppressWarnings("unchecked")
    static String run(List<String> names, boolean reactive) {
        List<String> calls = new ArrayList<>();
        Health health;
        if (reactive) {
            var client = mock(com.mongodb.reactivestreams.client.MongoClient.class);
            when(client.listDatabaseNames()).thenReturn(Flux.fromIterable(names));
            when(client.getDatabase(anyString())).thenAnswer(call -> {
                String name = call.getArgument(0);
                var db = mock(com.mongodb.reactivestreams.client.MongoDatabase.class);
                when(db.runCommand(any(Document.class))).thenAnswer(cmd -> Mono.fromSupplier(() -> hello(cmd.getArgument(0), name, calls)));
                return db;
            });
            health = new MongoReactiveHealthIndicator(client).health().block();
        } else {
            MongoClient client = mock(MongoClient.class);
            MongoIterable<String> iterable = mock(MongoIterable.class);
            doAnswer(call -> { names.forEach((Consumer<String>) call.getArgument(0)); return null; })
                    .when(iterable).forEach(any());
            when(client.listDatabaseNames()).thenReturn(iterable);
            when(client.getDatabase(anyString())).thenAnswer(call -> {
                String name = call.getArgument(0);
                MongoDatabase db = mock(MongoDatabase.class);
                when(db.runCommand(any(Document.class))).thenAnswer(cmd -> hello(cmd.getArgument(0), name, calls));
                return db;
            });
            health = new MongoHealthIndicator(client).health();
        }
        var listed = (List<?>) health.getDetails().get("databases");
        boolean complete = listed != null && listed.size() == names.size() && new HashSet<>(listed).equals(new HashSet<>(names));
        return health.getStatus().getCode() + ":" + (complete ? "complete" : "incomplete")
                + ":" + health.getDetails().get("maxWireVersion") + ":" + String.join(",", calls);
    }
    static String both(List<String> names) { return run(names, false) + "/" + run(names, true); }
    public static String observe(String[] args) {
        if (args[0].equals("intent")) return both(List.of("test", "admin"));
        if (args[0].equals("control")) return both(List.of("test"));
        var names = new ArrayList<String>();
        for (int i = 0; i < 8; i++) names.add("fixture" + i);
        names.add("admin");
        String last = both(names);
        Collections.rotate(names, 1);
        return last + ";" + both(names);
    }
}
