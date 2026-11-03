package fixtures.spring;

import java.util.function.Supplier;

/** A helper that runs a lambda: what the lambda reaches is reached from the caller. Not a bean. */
public final class Work {
    public <T> T run(Supplier<T> body) {
        return body.get();
    }
}
