package claims;

/**
 * Countermodels of a write set (`prove --writes`, a first effect contract): beans whose setter writes more than its
 * name says, each in a way a frame must see, and the honest one it is told apart from. Each bean is made by its one
 * constructor from any field values, so a frame proved of it holds in every state the bean can be in. {@code main}
 * shows on a JVM what each setter leaves.
 *
 * <p>The application's side: a request renames an account ({@code adminAfterRename} and the others), and an effect
 * contract of the setter stands in for the call. The setters below the honest one each make the contract's use
 * unsound in one way (outside its bounds, by what it reads of the receiver or of a static field, by identity, through
 * a subclass): on a JVM each rename grants admin.
 */
public final class Frames {
    private Frames() {}

    /** Where a setter can write that is no field of its receiver: a static field. */
    static String lastName;

    /** A switch a setter reads, false until a caller sets it, in a class with no initializer of its own. */
    static final class Switch {
        private Switch() {}

        static boolean trusting;
    }

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

    /** Writes the protected field on a name longer than three units: within a bound of three, it writes its own. */
    public static final class Lengthy {
        String displayName;
        boolean admin;

        public Lengthy(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            if (name.length() > 3) {
                this.admin = true;
            }
        }
    }

    /**
     * Grants admin once a role is set, which its constructor never does: from any state the constructor makes, the
     * setter writes its own field alone.
     */
    public static final class Promoting {
        String displayName;
        boolean admin;
        String role;

        public Promoting(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setRole(String role) {
            this.role = role;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            if (this.role != null) {
                this.admin = true;
            }
        }
    }

    /** Grants admin while a static switch is on, which it is not in a fresh class. */
    public static final class Trusting {
        String displayName;
        boolean admin;

        public Trusting(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            if (Switch.trusting) {
                this.admin = true;
            }
        }
    }

    /** Grants admin for the literal itself, by identity: a String a proof makes up is never that object. */
    public static final class Matching {
        String displayName;
        boolean admin;

        public Matching(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        @SuppressWarnings("StringEquality")
        public void setDisplayName(String name) {
            this.displayName = name;
            if (name == "root") {
                this.admin = true;
            }
        }
    }

    /** An honest setter that tells its subclasses it renamed: a hook that does nothing here. */
    public static class Base {
        String displayName;
        boolean admin;

        public Base(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void setDisplayName(String name) {
            this.displayName = name;
            renamed();
        }

        protected void renamed() {}
    }

    /** Inherits the setter and overrides the hook: the setter it runs is the base's, and it grants admin. */
    public static final class Sneaky extends Base {
        public Sneaky(String displayName, boolean admin) {
            super(displayName, admin);
        }

        @Override
        protected void renamed() {
            this.admin = true;
        }
    }

    /**
     * Writes the other account's protected field, which its write set names, and its own name only where the other
     * account is itself: a frame proved of two distinct accounts says nothing of one passed twice.
     */
    public static final class Linking {
        String displayName;
        boolean admin;

        public Linking(String displayName, boolean admin) {
            this.displayName = displayName;
            this.admin = admin;
        }

        public void link(Linking other) {
            other.admin = true;
            if (this == other) {
                this.displayName = "self";
            }
        }
    }

    /** Renames another bean, of a nested class: an effect contract over it names that class in its stub. */
    public static final class Mentor {
        public Mentor() {}

        public void adopt(Honest mentee, String name) {
            mentee.displayName = name;
        }
    }

    /** A mentor renames an admin: it stays one, under the new name. */
    public static boolean adoptedRename(String name) {
        Honest account = new Honest("", true);
        new Mentor().adopt(account, name);
        return account.admin && account.displayName == name;
    }

    /** The application: a request renames a fresh account, which is no admin; whether it is one after. */
    public static boolean adminAfterRename(String name) {
        Adversarial account = new Adversarial("", false);
        account.setDisplayName(name);
        return account.admin;
    }

    /** The same over the honest bean, which is an admin: it is one after, under the new name. */
    public static boolean honestRename(String name) {
        Honest account = new Honest("", true);
        account.setDisplayName(name);
        return account.admin && account.displayName == name;
    }

    public static boolean lengthyAdminAfterRename(String name) {
        Lengthy account = new Lengthy("", false);
        account.setDisplayName(name);
        return account.admin;
    }

    public static boolean promotedAfterRename(String role, String name) {
        Promoting account = new Promoting("", false);
        account.setRole(role);
        account.setDisplayName(name);
        return account.admin;
    }

    public static boolean trustedAfterRename(String name) {
        Switch.trusting = true;
        Trusting account = new Trusting("", false);
        account.setDisplayName(name);
        return account.admin;
    }

    public static boolean matchedAfterRename(boolean root) {
        Matching account = new Matching("", false);
        account.setDisplayName(root ? "root" : "user");
        return account.admin;
    }

    public static boolean sneakyAfterRename(boolean sneaky, String name) {
        Base account = sneaky ? new Sneaky("", false) : new Base("", false);
        account.setDisplayName(name);
        return account.admin;
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
        out.append(" rename.admin=").append(adminAfterRename("admin:")).append(" honest.rename=").append(honestRename("x"));
        out.append(" lengthy.admin=").append(lengthyAdminAfterRename("abcd")).append(" promoted.admin=").append(promotedAfterRename("r", "x"));
        out.append(" matched.admin=").append(matchedAfterRename(true)).append(" sneaky.admin=").append(sneakyAfterRename(true, "x"));
        out.append(" trusted.admin=").append(trustedAfterRename("x"));
        Linking linking = new Linking("", false);
        linking.link(linking);
        out.append(" linked.name=").append(linking.displayName);
        System.out.println(out);
    }
}
