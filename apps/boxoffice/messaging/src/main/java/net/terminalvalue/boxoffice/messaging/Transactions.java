package net.terminalvalue.boxoffice.messaging;

import com.mongodb.MongoException;
import java.time.Duration;
import java.util.function.Supplier;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Runs work in a MongoDB transaction, and runs it again when MongoDB reports a transient error, typically a write
 * conflict with a concurrent transaction on the same document. The work must therefore be safe to repeat, which it
 * is when every write is conditional on the state it read.
 */
public final class Transactions {

    private final TransactionTemplate template;
    private final int maxAttempts;
    private final Duration backoff;

    public Transactions(TransactionTemplate template, int maxAttempts, Duration backoff) {
        this.template = template;
        this.maxAttempts = maxAttempts;
        this.backoff = backoff;
    }

    public <T> T run(Supplier<T> work) {
        for (int attempt = 1; ; attempt++) {
            try {
                return template.execute(_ -> work.get());
            } catch (RuntimeException e) {
                if (attempt >= maxAttempts || !isTransient(e)) {
                    throw e;
                }
                pause(attempt);
            }
        }
    }

    public void run(Runnable work) {
        run(() -> {
            work.run();
            return null;
        });
    }

    /** Throws unless the caller runs inside a transaction. Guards writes that must be atomic with others. */
    public static void requireActive(String what) {
        if (!TransactionSynchronizationManager.isActualTransactionActive()) {
            throw new IllegalStateException(what + " must run inside a transaction");
        }
    }

    static boolean isTransient(Throwable error) {
        for (Throwable t = error; t != null; t = t.getCause()) {
            if (t instanceof MongoException mongo && mongo.hasErrorLabel(MongoException.TRANSIENT_TRANSACTION_ERROR_LABEL)) {
                return true;
            }
        }
        return false;
    }

    private void pause(int attempt) {
        try {
            Thread.sleep(backoff.multipliedBy(attempt));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted while retrying a transaction", e);
        }
    }
}
