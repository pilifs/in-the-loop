package fixtures.spring;

/** An interface the flow calls: the walk goes to the implementation. */
public interface Notifier {
    void notify(String who);
}
