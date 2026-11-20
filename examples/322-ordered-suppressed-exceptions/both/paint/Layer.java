package paint;

public final class Layer implements AutoCloseable {
    private final String tag; private final boolean fails; private final Outcome out;
    Layer(String tag,boolean fails,Outcome out) { this.tag=tag;this.fails=fails;this.out=out; }
    public void close() { out.trace[out.closed++]=tag; if(fails)throw new Tagged(tag); }
}
