package fixtures.spring;

import java.util.Optional;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.util.Assert;
import org.springframework.web.server.ResponseStatusException;

/** What each route throws: through a supplier, an `Assert`, a catch that swallows, one that rethrows, one that wraps. */
@Service
public class FailureFlow {
    private final NoteRepository notes;

    public FailureFlow(NoteRepository notes) {
        this.notes = notes;
    }

    /** The supplier's exception is thrown by `orElseThrow`. */
    public String find(String id) {
        return notes.findById(id).map(NoteDocument::text).orElseThrow(() -> new MissingException(id));
    }

    public void expire(String id) {
        if (id.isEmpty()) {
            throw new ExpiredException(id);
        }
    }

    /** `Assert` throws for the caller; the catch takes the parse failure and throws something else. */
    public void check(String id) {
        Assert.hasText(id, "id");
        try {
            Integer.parseInt(id);
        } catch (NumberFormatException e) {
            throw new StaleException(e.getMessage());
        }
    }

    /** The catch swallows what `expire` throws. */
    public void guarded(String id) {
        try {
            expire(id);
        } catch (ExpiredException e) {
            System.out.println(e.getMessage());
        }
    }

    /** The catch rethrows: everything passes through. */
    public void retried(String id) {
        try {
            expire(id);
        } catch (RuntimeException e) {
            System.out.println(e.getMessage());
            throw e;
        }
    }

    /** The catch wraps: the wrapper is thrown, the cause is not. */
    public void wrapped(String id) {
        try {
            expire(id);
        } catch (ExpiredException e) {
            throw new IllegalStateException("wrapped", e);
        }
    }

    /** The status travels with the exception. */
    public String gone(String id) {
        throw new ResponseStatusException(HttpStatus.GONE, id);
    }

    /** An empty optional: the JDK's exception, a 500. */
    public String pick(Optional<String> value) {
        return value.orElseThrow();
    }

    /** On another thread: nothing reaches the caller. */
    @Async
    public void later(String id) {
        throw new ExpiredException(id);
    }
}
