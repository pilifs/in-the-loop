package ec;

/** Overrides the hook, and grants itself admin. */
public final class Rogue extends Peer {
    public Rogue(boolean admin) {
        super(admin);
    }

    @Override
    protected void linked() {
        this.admin = true;
    }
}
