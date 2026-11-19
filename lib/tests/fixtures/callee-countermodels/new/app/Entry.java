package app;

import java.nio.charset.StandardCharsets;

/** The new version. The entries of the callee countermodels: each converts the password as example 307's new
 * revision does and calls a callee that is the same code in both versions (`Hash`, `Wiping`, `Counting`, `Pairing`), or
 * the same instructions over code that is not (`Seeded`, `Helped`). The other version is `../../old/app/Entry.java`;
 * the README says what a JVM gives for each pair and what a check may say. */
public final class Entry {
    private Entry() {}

    static byte[] bytes(String password) {
        return password.getBytes(StandardCharsets.UTF_8);
    }

    /** The same conversion and the same call, written as three statements: other instructions, the same values. */
    public static String same(String password, String salt) {
        byte[] b = bytes(password);
        String digest = Hash.digest(b, salt);
        return digest;
    }

    /** The same bytes through a copy of the array the loop below makes: equal content that is not the same value
     * written twice. */
    public static String copied(String password, String salt) {
        byte[] b = bytes(password);
        byte[] copy = new byte[b.length];
        for (int i = 0; i < b.length; i++) {
            copy[i] = b[i];
        }
        return Hash.digest(copy, salt);
    }

    /** Two calls with the same arguments, whose results are two objects with the same content. */
    public static String twice(String password, String salt) {
        String first = Hash.digest(bytes(password), salt);
        String second = Hash.digest(bytes(password), salt);
        return first == second ? "one" : first.equals(second) ? "fresh" : "other";
    }

    /** The table is written before the call. */
    public static String table(String password, String salt) {
        byte[] b = bytes(password);
        Hash.poke(0);
        return Hash.digest(b, salt);
    }

    /** The call; `Seed` is what differs. */
    public static String seeded(String password, String salt) {
        return Seeded.digest(bytes(password), salt);
    }

    /** The call; `Helped`'s helper is what differs. */
    public static String helped(String password, String salt) {
        return Helped.digest(bytes(password), salt);
    }

    /** The callee is given a copy of the array that is read afterwards. */
    public static String wiped(String password, String salt) {
        byte[] b = bytes(password);
        String digest = Wiping.digest(b.clone(), salt);
        return b.length > 0 && b[0] == 0 ? "wiped" : digest;
    }

    /** Two calls with the same arguments; the second one's result. */
    public static String counted(String password, String salt) {
        byte[] b = bytes(password);
        Counting.digest(b, salt);
        return Counting.digest(b, salt);
    }

    /** The callee's exception is not caught. */
    public static String caught(String password, String salt) {
        return Hash.digest(bytes(password), salt);
    }

    /** One array given twice. */
    public static String aliased(String password, String salt) {
        byte[] b = bytes(password);
        return Pairing.digest(b, b, salt);
    }

    /** The same call in three statements, as `same`; the callee reads its rounds with `Integer.parseInt`. */
    public static String parsed(String password, String salt) {
        byte[] b = bytes(password);
        String digest = Parsing.digest(b, salt);
        return digest;
    }

    /** A shared loop over an integer, within the one-function rule. */
    public static int scalar(String password, String salt) {
        int length = password == null ? 0 : password.length();
        return Hash.rounds(length);
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
                case "scalar": got = Integer.toString(scalar(password, salt)); break;
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
