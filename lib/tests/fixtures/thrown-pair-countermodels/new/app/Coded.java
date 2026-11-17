package app;

/** A failure that carries a status code, of one name and one superclass in both versions. */
public class Coded extends RuntimeException {
    public final int code;

    public Coded(int code) {
        super("refused");
        this.code = code;
    }
}
