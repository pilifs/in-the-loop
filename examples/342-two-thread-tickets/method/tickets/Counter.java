package tickets;

public class Counter {
    private int issued;
    public synchronized int take() { return ++issued; }
    protected void between() {}
    public int issued() { return issued; }
}
