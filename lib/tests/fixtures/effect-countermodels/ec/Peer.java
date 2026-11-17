package ec;

/** An argument told it was linked: a hook that does nothing in this class. */
public class Peer {
    public boolean admin;

    public Peer(boolean admin) {
        this.admin = admin;
    }

    protected void linked() {}
}
