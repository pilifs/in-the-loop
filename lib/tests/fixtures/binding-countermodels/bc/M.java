package bc;

/**
 * The entry points of the binding countermodels, and a {@code main} that prints what each returns on a JVM:
 * {@code java -cp CLASSES bc.M}.
 */
public class M {
    /** Reads Rehooked's static, which initializes it, then calls Hooks' lambda: 5 on a JVM. */
    public static int rehooked() {
        int k = Rehooked.k;
        return Hooks.hook.getAsInt();
    }

    /** Reads Boxed's static, which initializes it, then the Box that Boxes holds: 5 on a JVM. */
    public static int boxed() {
        int k = Boxed.k;
        return Boxes.BOX.value;
    }

    /** Reads Relocaled's static, which initializes it, then lowers "I": 305 on a JVM, whose default is then Turkish. */
    public static int relocaled() {
        int k = Relocaled.k;
        return "I".toLowerCase().charAt(0);
    }

    /** All three in one JVM, relocaled last, since its initializer changes the default locale for what follows. */
    public static void main(String[] args) {
        System.out.println("rehooked=" + rehooked() + " boxed=" + boxed() + " relocaled=" + relocaled());
    }
}
