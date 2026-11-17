package app;

import java.nio.charset.StandardCharsets;

/** The previous version. The entries of the callee countermodels: each converts the password as example 307's new
 * revision does and calls a callee that is the same code in both versions (`Hash`, `Wiping`, `Counting`, `Pairing`), or
 * the same instructions over code that is not (`Seeded`, `Helped`). The other version is `../../new/app/Entry.java`;
 * the README says what a JVM gives for each pair and what a check may say. */
public final class Entry {
    private Entry() {}

    static byte[] bytes(String password) {
        return password.getBytes(StandardCharsets.UTF_8);
    }

    /** The shape of 307's change: the conversion and the call, in one expression. */
    public static String same(String password, String salt) {
        return Hash.digest(bytes(password), salt);
    }

    /** The conversion and the call. */
    public static String copied(String password, String salt) {
        return Hash.digest(bytes(password), salt);
    }

    /** One call. */
    public static String twice(String password, String salt) {
        String first = Hash.digest(bytes(password), salt);
        return first.isEmpty() ? "none" : "fresh";
    }

    /** The call as it is. */
    public static String table(String password, String salt) {
        return Hash.digest(bytes(password), salt);
    }

    /** The call; `Seed` is what differs. */
    public static String seeded(String password, String salt) {
        return Seeded.digest(bytes(password), salt);
    }

    /** The call; `Helped`'s helper is what differs. */
    public static String helped(String password, String salt) {
        return Helped.digest(bytes(password), salt);
    }

    /** The callee is given the array that is read afterwards. */
    public static String wiped(String password, String salt) {
        byte[] b = bytes(password);
        String digest = Wiping.digest(b, salt);
        return b.length > 0 && b[0] == 0 ? "wiped" : digest;
    }

    /** One call. */
    public static String counted(String password, String salt) {
        return Counting.digest(bytes(password), salt);
    }

    /** The callee's exception for an empty salt is caught. */
    public static String caught(String password, String salt) {
        byte[] b = bytes(password);
        try {
            return Hash.digest(b, salt);
        } catch (IllegalArgumentException e) {
            return "bad";
        }
    }

    /** Two arrays of the same bytes. */
    public static String aliased(String password, String salt) {
        byte[] b = bytes(password);
        return Pairing.digest(b, bytes(password), salt);
    }

    /** The conversion and the call; the callee reads its rounds with `Integer.parseInt`. */
    public static String parsed(String password, String salt) {
        return Parsing.digest(bytes(password), salt);
    }

    /** Each method on a few inputs, one line a method: `name password/salt=result ...`. An exception is its
     * class's name. Each call starts from a state no other call has touched only for the first input: the
     * differences shown are those of one call each, in a JVM of its own (the README's table, `check.py`). */
    public static void main(String[] args) {
        String password = args[1].equals("null") ? null : args[1].equals("empty") ? "" : args[1];
        String salt = args[2].equals("null") ? null : args[2].equals("empty") ? "" : args[2];
        String got;
        try {
            switch (args[0]) {
                case "same": got = same(password, salt); break;
                case "copied": got = copied(password, salt); break;
                case "twice": got = twice(password, salt); break;
                case "table": got = table(password, salt); break;
                case "seeded": got = seeded(password, salt); break;
                case "helped": got = helped(password, salt); break;
                case "wiped": got = wiped(password, salt); break;
                case "counted": got = counted(password, salt); break;
                case "caught": got = caught(password, salt); break;
                case "aliased": got = aliased(password, salt); break;
                case "parsed": got = parsed(password, salt); break;
                default: throw new IllegalStateException(args[0]);
            }
        } catch (RuntimeException e) {
            got = e.getClass().getName();
        }
        System.out.println(got);
    }
}
