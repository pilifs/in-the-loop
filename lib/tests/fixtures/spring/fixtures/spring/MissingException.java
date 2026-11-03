package fixtures.spring;

/** An application exception that {@link ApiErrors} maps to a 404. */
public class MissingException extends RuntimeException {
    public MissingException(String id) {
        super("no " + id);
    }
}
