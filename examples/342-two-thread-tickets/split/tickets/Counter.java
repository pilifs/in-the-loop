package tickets;

public class Counter {
    private int issued;
    public int take() {
        int saved;
        synchronized (this) { saved = issued; }
        between();
        synchronized (this) { issued = saved + 1; return issued; }
    }
    protected void between() {}
    public int issued() { return issued; }
}
