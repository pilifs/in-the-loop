package sc;

/** A bean with a setter that an effect contract stands in for: `writes: this.level`, `assert: this.level == level`. */
public class Bean {
    public int level;

    public void setLevel(int level) {
        this.level = level;
    }
}
