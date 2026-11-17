package cc;

/**
 * Countermodels of an effect contract at a call past its fix (the state stream's nslmqyry): a contract reads no field
 * of an object that was there before the call unless the field is final, but a final instance field is what its
 * constructor made of the state it ran in, and of the constructor it ran.
 */
public final class Held {
    private Held() {}

    /** A setting a caller may change before it makes a bean. */
    public static final class Config {
        private Config() {}

        public static boolean locked;
    }

    /** Takes the setting into a final field when it is made: the harness makes it where the setting is false. */
    public static final class Snapshot {
        final boolean locked = Config.locked;
        public int level;

        public Snapshot(int level) {
            this.level = level;
        }

        public void setLevel(int level) {
            this.level = locked ? 0 : level;
        }
    }

    /** A final flag one constructor sets and the other leaves false. */
    public static final class Chosen {
        final boolean locked;
        public int level;

        public Chosen(int level) {
            this.locked = false;
            this.level = level;
        }

        public Chosen(int level, boolean locked) {
            this.locked = locked;
            this.level = level;
        }

        public void setLevel(int level) {
            this.level = locked ? 0 : level;
        }
    }

    /** A final field made from the argument's setting: an argument's final field, the same way. */
    public static final class Source {
        final int scale = Config.locked ? 0 : 1;

        public Source() {}
    }

    public static final class Scaled {
        public int level;

        public Scaled(int level) {
            this.level = level;
        }

        public void setFrom(Source source, int level) {
            this.level = source.scale * level;
        }
    }

    public static int snapshotLevel(int level) {
        Config.locked = true;
        Snapshot bean = new Snapshot(1);
        Config.locked = false;
        bean.setLevel(level);
        return bean.level;
    }

    public static int chosenLevel(int level) {
        Chosen bean = new Chosen(1, true);
        bean.setLevel(level);
        return bean.level;
    }

    public static int scaledLevel(int level) {
        Config.locked = true;
        Source source = new Source();
        Config.locked = false;
        Scaled bean = new Scaled(1);
        bean.setFrom(source, level);
        return bean.level;
    }

    public static void main(String[] args) {
        System.out.println("snapshot=" + snapshotLevel(5) + " chosen=" + chosenLevel(5) + " scaled=" + scaledLevel(5));
    }
}
