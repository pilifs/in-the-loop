package fc;

/**
 * Countermodels of a write set (`prove --writes`, the state stream's first effect contract, `qrqtplwq`): methods
 * that write a field the set does not name in a way the frame, read only after a normal return of a call on
 * distinct inputs, does not see. {@code main} prints what each leaves on a JVM.
 */
public final class Framed {
    private Framed() {}

    /** A bean with a protected field. */
    public static final class Bean {
        String displayName;
        boolean admin;

        public Bean(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        /**
         * Writes the protected field first and puts it back only when it returns: an exception in between leaves
         * it written.
         */
        public void rename(String name, int length) {
            boolean was = this.admin;
            this.admin = true;
            if (length < 0) {
                throw new IllegalArgumentException("negative");
            }
            this.displayName = name;
            this.admin = was;
        }

        /** Writes another bean's protected field: the receiver's, when the other bean is the receiver. */
        public void promote(Bean other) {
            other.admin = true;
        }
    }

    /** Writes {@code to.admin}; {@code from} is the same object when the caller passes one bean twice. */
    public static void grant(Bean from, Bean to) {
        to.admin = true;
    }

    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        Bean renamed = new Bean("a", false);
        try {
            renamed.rename("b", -1);
        } catch (IllegalArgumentException e) {
            out.append("rename.threw=true ");
        }
        out.append("rename.admin=").append(renamed.admin);
        Bean self = new Bean("a", false);
        self.promote(self);
        out.append(" promote.this.admin=").append(self.admin);
        Bean both = new Bean("a", false);
        grant(both, both);
        out.append(" grant.from.admin=").append(both.admin);
        System.out.println(out);
    }
}
