package ec;

/**
 * Writes one field of two beans, the argument's first and then its own. A top-level class: the effect stub names a
 * nested parameter class with its `$` (`ec.Uses$Pair`), which javac does not take.
 */
public final class Pair {
    public int level;

    public Pair(int level) {
        this.level = level;
    }

    public void setBoth(Pair other, int mine, int theirs) {
        other.level = theirs;
        this.level = mine;
    }
}
