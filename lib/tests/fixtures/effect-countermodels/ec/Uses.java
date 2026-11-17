package ec;

/**
 * Countermodels of an effect contract at a call (the state stream's `vwktulky`): a setter's checked write set stands
 * in for its calls by the writes it states. Each setter below has a contract the checker proves, and each caller
 * calls it where the call does something the contract does not say. {@code main} prints what a JVM says.
 */
public final class Uses {
    private Uses() {}

    /** A setting a caller may change before the bean's class is first used. */
    public static final class Config {
        private Config() {}

        public static boolean locked;
    }

    /** Takes the setting once, when its class is initialized, into a final static, which a contract may read. */
    public static final class Locked {
        static final boolean LOCKED = Config.locked;

        public int level;

        public Locked(int level) {
            this.level = level;
        }

        public void setLevel(int level) {
            this.level = LOCKED ? 0 : level;
        }
    }

    /** Counts its links and tells the peer: of a Peer, it writes nothing but its own count. */
    public static final class Linking {
        public int links;

        public Linking(int links) {
            this.links = links;
        }

        public void link(Peer peer, int links) {
            this.links = links;
            peer.linked();
        }
    }

    /** Sets admin, and puts it back unless it throws. */
    public static final class Failing {
        public int level;
        public boolean admin;

        public Failing(int level, boolean admin) {
            this.level = level;
            this.admin = admin;
        }

        public void setLevel(int level) {
            boolean was = this.admin;
            this.admin = true;
            if (level < 0) {
                throw new IllegalArgumentException("negative");
            }
            this.level = level;
            this.admin = was;
        }
    }

    /** The caller sets the switch before the bean's class is initialized: the level is not the one it sets. */
    public static int lockedLevel(int level) {
        Config.locked = true;
        Locked bean = new Locked(1);
        bean.setLevel(level);
        return bean.level;
    }

    /** One bean as both: its level is the receiver's, the last written. */
    public static int pairedLevel(int mine, int theirs) {
        Pair bean = new Pair(0);
        bean.setBoth(bean, mine, theirs);
        return bean.level;
    }

    /** A Rogue linked: it is an admin after. */
    public static boolean linkedAdmin(int links) {
        Linking linking = new Linking(0);
        Peer peer = new Rogue(false);
        linking.link(peer, links);
        return peer.admin;
    }

    /** A negative level caught: the bean is an admin after. */
    public static boolean failedAdmin(int level) {
        Failing bean = new Failing(0, false);
        try {
            bean.setLevel(level);
        } catch (IllegalArgumentException e) {
            // the caller goes on
        }
        return bean.admin;
    }

    public static void main(String[] args) {
        System.out.println("locked=" + lockedLevel(5) + " paired=" + pairedLevel(1, 2) + " linked.admin=" + linkedAdmin(1) + " failed.admin=" + failedAdmin(-1));
    }
}
