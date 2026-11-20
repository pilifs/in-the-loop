package tickets;

public class Counter {
    private int issued;
    public int take() { synchronized (this) { return ++issued; } }
    protected void between() {}
    public int issued() { return issued; }
}
