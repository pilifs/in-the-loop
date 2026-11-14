package inloop.p307;

import org.springframework.security.crypto.bcrypt.BCrypt;

/** 307's concrete control: it calls the original BCrypt.hashpw(String, String) of whichever spring-security-crypto
 * classes are on the class path, once per probe, and prints one JSON line per probe: the arguments as given and the
 * outcome as the JVM gave it (the returned String, or the exception's class). It decides nothing; controls/oracle.py
 * reads the lines. It maps, normalizes and replaces nothing, so the original bytecode decides; in particular it never
 * encodes the password itself, and never calls checkpw (a match against the stored hash is the oracle's comparison of
 * the returned String with it).
 *
 * <p>Arguments come in pairs, password then salt, each {@code null} or {@code u} followed by the String's UTF-16 code
 * units in hex, comma-separated ({@code u} alone is the empty String): code units, not characters, so isolated and
 * reversed surrogates reach the method exactly. {@code python3 -I controls/oracle.py argv} prints them.
 *
 * <p>Compiled with {@code --release 21} against one revision's BCrypt class; the method's descriptor is the same at
 * both commits, so one driver JAR runs on either. Only a RuntimeException is recorded as an outcome, by class (its
 * message is not observed: since JDK 14 a NullPointerException's message names the method called on null, and that
 * method is what the patch changes). An Error ends the run (the before revision's AssertionError for an unsupported
 * UTF-8 among them, which no conforming JDK can reach), and the oracle reports the probes it lacks as an incomplete
 * replay, never as a result. */
public final class HashpwDriver {
    private HashpwDriver() {
    }

    static String decode(String arg) {
        if (arg.equals("null")) {
            return null;
        }
        if (!arg.startsWith("u")) {
            throw new IllegalArgumentException("an argument is null or u<hex code units>: " + arg);
        }
        String hex = arg.substring(1);
        if (hex.isEmpty()) {
            return "";
        }
        String[] parts = hex.split(",", -1);
        char[] units = new char[parts.length];
        for (int i = 0; i < parts.length; i++) {
            int unit = Integer.parseInt(parts[i], 16);
            if (unit < 0 || unit > 0xFFFF) {
                throw new IllegalArgumentException("not a UTF-16 code unit: " + parts[i]);
            }
            units[i] = (char) unit;
        }
        return new String(units);
    }

    static String quote(String s) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                out.append('\\').append(c);
            } else if (c < 0x20 || c > 0x7E) {
                out.append(String.format("\\u%04x", (int) c));
            } else {
                out.append(c);
            }
        }
        return out.append('"').toString();
    }

    public static void main(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException("arguments come in pairs, password then salt");
        }
        for (int i = 0; i < args.length; i += 2) {
            String password = decode(args[i]);
            String salt = decode(args[i + 1]);
            String outcome;
            try {
                String hashed = BCrypt.hashpw(password, salt);
                outcome = "\"returned\",\"value\":" + (hashed == null ? "null" : quote(hashed));
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            System.out.println("{\"password\":\"" + args[i] + "\",\"salt\":\"" + args[i + 1] + "\",\"outcome\":" + outcome + "}");
        }
    }
}
