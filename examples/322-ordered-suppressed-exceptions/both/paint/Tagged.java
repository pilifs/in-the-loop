package paint;

public final class Tagged extends RuntimeException {
    public final String tag;
    Tagged(String tag) { super(tag); this.tag=tag; }
}
