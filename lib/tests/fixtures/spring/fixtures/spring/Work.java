package fixtures.spring;

import java.util.function.Supplier;
import org.springframework.transaction.support.TransactionTemplate;

/** A helper that runs a lambda: what the lambda reaches is reached from the caller. Not a bean. */
public final class Work {
    public <T> T run(Supplier<T> body) {
        return body.get();
    }

    /** A transaction runner: the lambda runs inside the transaction the template opens. */
    public <T> T atomically(TransactionTemplate transactions, Supplier<T> body) {
        return transactions.execute(status -> body.get());
    }
}
