package sc;

/** What a JVM says: f(2) is -1, and touch(5) leaves the bean Touch holds at level 5. */
public class M {
    public static void main(String[] args) {
        int f = Store.f(2);
        Touch.touch(5);
        System.out.println("f=" + f + " held=" + Touch.HELD.level);
    }
}
