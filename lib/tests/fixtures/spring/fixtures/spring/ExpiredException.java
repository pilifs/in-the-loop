package fixtures.spring;

/** An application exception nothing maps: a 500 wherever it reaches a route. */
public class ExpiredException extends RuntimeException {
    public ExpiredException(String id) {
        super(id + " has expired");
    }
}
