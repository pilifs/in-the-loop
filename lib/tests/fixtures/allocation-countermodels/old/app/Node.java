package app;

/** g calls f, which an override calls back through. */
public class Node {
    public int f(int k) {
        return k;
    }

    public int g(int k) {
        return f(k - 1);
    }
}
