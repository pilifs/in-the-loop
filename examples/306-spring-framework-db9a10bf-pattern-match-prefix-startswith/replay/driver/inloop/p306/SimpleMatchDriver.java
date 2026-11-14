package inloop.p306;

import org.springframework.util.PatternMatchUtils;

/** 306's concrete control: it calls the original PatternMatchUtils.simpleMatch(String, String) of whichever spring-core
 * JAR is on the class path, once per probe, and prints one JSON line per probe: the arguments as given and the
 * outcome as the JVM gave it (the boolean, or the exception's class). It decides nothing; controls/oracle.py reads the
 * lines. It maps, normalizes and replaces nothing, so the original bytecode decides.
 *
 * <p>Arguments come in pairs, pattern then str, each {@code null} or {@code u} followed by the String's UTF-16 code
 * units in hex, comma-separated ({@code u} alone is the empty String): code units, not characters, so isolated
 * surrogates reach the method exactly. {@code python3 -I controls/oracle.py argv} prints them.
 *
 * <p>Compiled with {@code --release 21} against one release's spring-core JAR; the method's descriptor is the same in
 * both, so one driver JAR runs on either. Only a RuntimeException is recorded as an outcome: an Error ends the run, and
 * the oracle reports the probes it lacks as an incomplete replay, never as a result. */
public final class SimpleMatchDriver {
    private SimpleMatchDriver() {
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

    public static void main(String[] args) {
        if (args.length % 2 != 0) {
            throw new IllegalArgumentException("arguments come in pairs, pattern then str");
        }
        for (int i = 0; i < args.length; i += 2) {
            String pattern = decode(args[i]);
            String str = decode(args[i + 1]);
            String outcome;
            try {
                outcome = "\"returned\",\"value\":" + PatternMatchUtils.simpleMatch(pattern, str);
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            System.out.println("{\"pattern\":\"" + args[i] + "\",\"str\":\"" + args[i + 1] + "\",\"outcome\":" + outcome + "}");
        }
    }
}
