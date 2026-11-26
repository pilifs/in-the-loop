import org.springframework.transaction.*;
import org.springframework.transaction.reactive.*;
import org.springframework.transaction.support.DefaultTransactionDefinition;

import reactor.core.publisher.*;

import java.util.*;
import java.util.concurrent.atomic.*;

public class PublicCaller {
    static class Manager extends AbstractReactiveTransactionManager {
        final Object transaction = new Object();
        final AtomicBoolean held = new AtomicBoolean();
        final boolean participating;
        final MonoProcessor<Void> gate = MonoProcessor.create();
        boolean gated, waiting;
        int commits, rollbacks, releases;

        Manager(boolean participating) {
            this.participating = participating;
            held.set(participating);
        }

        protected Object doGetTransaction(TransactionSynchronizationManager sm) {
            return transaction;
        }

        protected boolean isExistingTransaction(Object tx) {
            return participating;
        }

        protected Mono<Void> doBegin(
                TransactionSynchronizationManager sm, Object tx, TransactionDefinition d) {
            return Mono.fromRunnable(
                    () -> {
                        if (!held.compareAndSet(false, true))
                            throw new IllegalStateException("occupied");
                    });
        }

        protected Mono<Void> doCommit(
                TransactionSynchronizationManager sm, GenericReactiveTransaction status) {
            return Mono.fromRunnable(() -> commits++);
        }

        protected Mono<Void> doRollback(
                TransactionSynchronizationManager sm, GenericReactiveTransaction status) {
            return Mono.fromRunnable(() -> rollbacks++);
        }

        protected Mono<Void> doCleanupAfterCompletion(
                TransactionSynchronizationManager sm, Object tx) {
            return Mono.defer(
                    () -> {
                        waiting = true;
                        Mono<Void> ready = gated ? gate : Mono.empty();
                        return ready.then(
                                Mono.fromRunnable(
                                        () -> {
                                            if (!held.compareAndSet(true, false))
                                                throw new IllegalStateException(
                                                        "duplicate release");
                                            releases++;
                                        }));
                    });
        }

        String receipt() {
            boolean acquired = held.compareAndSet(false, true);
            if (acquired) held.set(false);
            return "c"
                    + commits
                    + ":r"
                    + rollbacks
                    + ":released"
                    + releases
                    + ":available="
                    + acquired;
        }
    }

    public static String observe(String[] args) {
        boolean participant = args[0].equals("participate"), rollback = args[0].equals("rollback");
        Manager manager = new Manager(participant);
        manager.gated = rollback;
        TransactionalOperator operator =
                TransactionalOperator.create(manager, new DefaultTransactionDefinition());
        final RuntimeException sentinel = new RuntimeException("fixture application error");
        List<Integer> values = new ArrayList<>();
        AtomicReference<Throwable> error = new AtomicReference<>();
        AtomicBoolean complete = new AtomicBoolean();
        Flux<Integer> source =
                rollback
                        ? Flux.just(1).concatWith(Mono.error(sentinel))
                        : participant ? Flux.just(7) : Flux.just(1, 2, 3, 4);
        operator.transactional(source).subscribe(values::add, error::set, () -> complete.set(true));
        if (!rollback)
            return values + ":" + (complete.get() ? "complete" : "other") + ":" + manager.receipt();
        boolean early = error.get() != null || complete.get(), waiting = manager.waiting;
        manager.gate.onComplete();
        return values
                + ":early="
                + early
                + ":waiting="
                + waiting
                + ":sentinel="
                + (error.get() == sentinel)
                + ":"
                + manager.receipt();
    }
}
