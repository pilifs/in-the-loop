import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import io.r2dbc.spi.*;
import org.reactivestreams.Publisher;
import reactor.core.publisher.Mono;
import org.springframework.r2dbc.connection.R2dbcTransactionManager;
import org.springframework.r2dbc.core.DatabaseClient;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.reactive.TransactionalOperator;
import org.springframework.transaction.support.DefaultTransactionDefinition;

public class PublicCaller {
    static final Duration LIMIT = Duration.ofSeconds(5);

    static class Factory implements ConnectionFactory {
        final ConnectionFactory physical;
        int commits, rollbacks, savepoints;
        Factory(ConnectionFactory physical) { this.physical = physical; }
        public ConnectionFactoryMetadata getMetadata() { return physical.getMetadata(); }
        public Publisher<? extends Connection> create() {
            return Mono.from(physical.create()).map(c -> (Connection)Proxy.newProxyInstance(Connection.class.getClassLoader(),
                    new Class<?>[]{Connection.class}, (proxy,m,args) -> {
                Object v;
                try { v = m.invoke(c,args); }
                catch (InvocationTargetException e) { throw e.getCause(); }
                return switch (m.getName()) {
                    case "commitTransaction" -> Mono.from((Publisher<?>)v).then().doOnSuccess(x -> commits++);
                    case "rollbackTransaction" -> Mono.from((Publisher<?>)v).then().doOnSuccess(x -> rollbacks++);
                    case "createSavepoint" -> Mono.from((Publisher<?>)v).then().doOnSuccess(x -> savepoints++);
                    default -> v;
                };
            }));
        }
    }

    static Mono<Void> insert(DatabaseClient client, String id) {
        return client.sql("INSERT INTO markers VALUES (:id)").bind("id",id).fetch().rowsUpdated()
                .doOnNext(n -> { if (n.intValue() != 1) throw new IllegalStateException("insert count"); }).then();
    }

    static String run(boolean scopes, boolean rollback) {
        var physical = ConnectionFactories.get("r2dbc:h2:mem:///savepoints");
        var keeper = Mono.from(physical.create()).block(LIMIT);
        try {
            var independent = DatabaseClient.create(physical);
            independent.sql("CREATE TABLE markers(id VARCHAR(8) PRIMARY KEY)").fetch().rowsUpdated().block(LIMIT);
            var factory = new Factory(physical);
            var work = DatabaseClient.create(factory);
            var manager = new R2dbcTransactionManager(factory);
            var nestedDefinition = new DefaultTransactionDefinition(TransactionDefinition.PROPAGATION_NESTED);
            var nested = TransactionalOperator.create(manager, nestedDefinition);
            var outer = TransactionalOperator.create(manager);
            var statuses = new ArrayList<Boolean>();
            String terminal;
            try {
                outer.execute(status -> {
                    Mono<Void> steps = insert(work,"A");
                    if (scopes) {
                        steps = steps.then(nested.execute(s -> {
                            statuses.add(s.isNested());
                            return insert(work,"B");
                        }).then()).then(nested.execute(s -> {
                            statuses.add(s.isNested());
                            return insert(work,"C").then(Mono.fromRunnable(s::setRollbackOnly));
                        }).then()).then(insert(work,"D"));
                    }
                    return rollback ? steps.then(Mono.fromRunnable(status::setRollbackOnly)) : steps;
                }).then().block(LIMIT);
                terminal = "complete";
            } catch (RuntimeException e) { terminal = e.getClass().getSimpleName(); }
            var rows = independent.sql("SELECT id FROM markers ORDER BY id").map((row, meta) -> row.get(0,String.class))
                    .all().collectList().block(LIMIT);
            boolean lost = statuses.contains(false);
            return "nested=" + statuses + " commits=" + factory.commits + " rollbacks=" + factory.rollbacks
                    + " savepoints=" + factory.savepoints + " rows=" + rows + " terminal=" + terminal + " lostOuter=" + lost;
        } finally { Mono.from(keeper.close()).block(LIMIT); }
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "nested" -> run(true,false);
            case "outer" -> run(false,false) + " / " + run(false,true);
            case "outer-rollback" -> run(true,true);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
