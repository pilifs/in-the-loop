import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import io.r2dbc.spi.*;
import reactor.core.publisher.*;
import org.springframework.r2dbc.connection.R2dbcTransactionManager;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.transaction.*;
import org.springframework.transaction.reactive.TransactionalOperator;

public class PublicCaller {
    static final Duration LIMIT = Duration.ofSeconds(5);
    static class Manager implements ReactiveTransactionManager {
        final R2dbcTransactionManager real;
        final List<String> actions = new ArrayList<>();
        final CountDownLatch finished = new CountDownLatch(1);
        Manager(ConnectionFactory physical) { real = new R2dbcTransactionManager(physical); }
        public Mono<ReactiveTransaction> getReactiveTransaction(TransactionDefinition d) { return real.getReactiveTransaction(d); }
        Mono<Void> observe(Mono<Void> action, String name) {
            return action.doOnSuccess(done -> { actions.add(name); finished.countDown(); });
        }
        public Mono<Void> commit(ReactiveTransaction t) { return observe(real.commit(t), "commit"); }
        public Mono<Void> rollback(ReactiveTransaction t) { return observe(real.rollback(t), "rollback"); }
    }

    static String run(String mode) throws Exception {
        ConnectionFactory physical = ConnectionFactories.get("r2dbc:h2:mem:///case_" + mode);
        // Keep the database alive while separate, unpooled operations open and close their connections.
        Connection keeper = Mono.from(physical.create()).block(LIMIT);
        try {
            var client = DatabaseClient.create(physical);
            client.sql("CREATE TABLE markers(id VARCHAR(16) PRIMARY KEY)").fetch().rowsUpdated().block(LIMIT);
            var manager = new Manager(physical);
            var operator = TransactionalOperator.create(manager);
            var designated = new IllegalStateException("designated source failure");
            Flux<String> tail = switch (mode) {
                case "normal" -> Flux.empty();
                case "error" -> Flux.error(designated);
                default -> Flux.never();
            };
            Flux<String> source = client.sql("INSERT INTO markers VALUES ('token')").fetch().rowsUpdated()
                    .map(count -> { if (count.intValue() != 1) throw new IllegalStateException("insert count"); return "token"; })
                    .concatWith(tail);
            Flux<String> wrapped = mode.equals("inside") ? operator.transactional(source.take(1)) : operator.transactional(source);
            if (mode.equals("outside")) wrapped = wrapped.take(1);
            var values = new ArrayList<String>();
            String terminal;
            if (mode.equals("cancel")) {
                wrapped.subscribe(new BaseSubscriber<String>() {
                    protected void hookOnNext(String v) { values.add(v); cancel(); }
                });
                terminal = "cancel";
            } else {
                try { wrapped.doOnNext(values::add).blockLast(LIMIT); terminal = "complete"; }
                catch (RuntimeException e) { if (e != designated) throw e; terminal = "designated"; }
            }
            if (!manager.finished.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("transaction cleanup timeout");
            var reader = DatabaseClient.create(physical);
            var rows = reader.sql("SELECT id FROM markers ORDER BY id").map((row, meta) -> row.get(0,String.class))
                    .all().collectList().block(LIMIT);
            return "values=" + values + " terminal=" + terminal + " actions=" + manager.actions + " rows=" + rows;
        } finally { Mono.from(keeper.close()).block(LIMIT); }
    }

    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "cancel" -> run("cancel");
            case "terminals" -> run("normal") + " / " + run("error");
            case "placement" -> "outside " + run("outside") + " / inside " + run("inside");
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
