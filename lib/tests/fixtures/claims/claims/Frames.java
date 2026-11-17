package claims;

/**
 * Countermodels of a write set (`prove --writes`, a first effect contract): beans whose setter writes more than its
 * name says, each in a way a frame must see, and the honest one it is told apart from. Each bean is made by its one
 * constructor from any field values, so a frame proved of it holds in every state the bean can be in. {@code main}
 * shows on a JVM what each setter leaves.
 */
public final class Frames {
    private Frames() {}

    /** Where a setter can write that is no field of its receiver: a static field. */
    static String lastName;

    /** An object that was there before any setter is called and is none of its inputs. */
    public static final Audit AUDIT = new Audit(0);

    public static final class Audit {
        int writes;

        public Audit(int writes) {
            this.writes = writes;
        }
    }

    /** The adversarial setter (the state stream's brief): the permitted property also writes the protected one. */
    public static final class Adversarial {
        String displayName;
        boolean admin;

        public Adversarial(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            this.admin = name.startsWith("admin:");
        }
    }

    /** Its honest twin: the same fields, a setter that writes its own field and nothing else. */
    public static final class Honest {
        String displayName;
        boolean admin;

        public Honest(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
        }
    }

    /** Writes the protected field and puts it back: the frame is about the state the call leaves, and holds. */
    public static final class Restoring {
        String displayName;
        boolean admin;

        public Restoring(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            boolean was = this.admin;
            this.admin = true;
            this.displayName = name;
            this.admin = was;
        }
    }

    /** Writes a field it does not name with a String of the same content: another object, so a write. */
    public static final class Copying {
        String displayName;
        String title;

        public Copying(String displayName, String title) {
            this.displayName = displayName;
            this.title = title;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            this.title = new StringBuilder().append(this.title).toString();
        }
    }

    /** Writes a static field beside its own: nothing the harness reads after the call shows it. */
    public static final class Remembering {
        String displayName;

        public Remembering(String displayName) {
            this.displayName = displayName;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            lastName = name;
        }
    }

    /** Writes a static field's object: the class may be initialized before the call or inside it. */
    public static final class Auditing {
        String displayName;

        public Auditing(String displayName) {
            this.displayName = displayName;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            AUDIT.writes++;
        }
    }

    /** Writes an object that was there before the call and is none of its inputs: one its receiver holds. */
    public static final class Counting {
        String displayName;
        Audit audit;

        public Counting(String displayName, Audit audit) {
            this.displayName = displayName;
            this.audit = audit;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            this.audit.writes++;
        }
    }

    /** Writes into an array it is given, which no field of an input is. */
    public static final class Filling {
        String displayName;

        public Filling(String displayName) {
            this.displayName = displayName;
        }

        public void setDisplayName(String name, int[] seen) {
            this.displayName = name;
            if (seen.length > 0) {
                seen[0] = 1;
            }
        }
    }

    /** What each setter leaves on a JVM: the fields it does not name, and the state outside its inputs. */
    public static void main(String[] args) {
        StringBuilder out = new StringBuilder();
        Adversarial adversarial = new Adversarial("", false);
        adversarial.setDisplayName("admin:");
        out.append("adversarial.admin=").append(adversarial.admin);
        Honest honest = new Honest("", false);
        honest.setDisplayName("admin:");
        out.append(" honest.admin=").append(honest.admin);
        Restoring restoring = new Restoring("", false);
        restoring.setDisplayName("admin:");
        out.append(" restoring.admin=").append(restoring.admin);
        Copying copying = new Copying("", "t");
        String title = copying.title;
        copying.setDisplayName("x");
        out.append(" copying.title.same=").append(copying.title == title).append(" copying.title.equal=").append(copying.title.equals(title));
        new Remembering("").setDisplayName("x");
        out.append(" lastName=").append(lastName);
        new Auditing("").setDisplayName("x");
        out.append(" audit.writes=").append(AUDIT.writes);
        Audit held = new Audit(0);
        Counting counting = new Counting("", held);
        counting.setDisplayName("x");
        out.append(" counting.audit.same=").append(counting.audit == held).append(" held.writes=").append(held.writes);
        int[] seen = {0};
        new Filling("").setDisplayName("x", seen);
        out.append(" seen[0]=").append(seen[0]);
        System.out.println(out);
    }
}
