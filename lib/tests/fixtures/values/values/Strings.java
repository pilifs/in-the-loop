package values;

/**
 * Small String methods over chars given as code units, for the values stream's conformance test
 * (lib/tests/values.rs, llm-dlc/loops/application-core-values.md): each is run on a JVM and in the interpreter, and
 * the two must give the same code units. They cover an isolated surrogate, a surrogate pair split and joined, an
 * embedded NUL and the replacement character, which a lossy conversion would confuse with an isolated surrogate.
 */
public final class Strings {
    private Strings() {
    }

    static String unit(int c) {
        return String.valueOf((char) c);
    }

    static String two(int a, int b) {
        return String.valueOf(new char[] {(char) a, (char) b});
    }

    static String made(int a, int b) {
        return new String(new char[] {(char) a, (char) b});
    }

    static String joined(int a, int b) {
        return "" + (char) a + (char) b;
    }

    static String withLiteral(int a) {
        return "<" + (char) a + ">";
    }

    static String built(int a, int b) {
        StringBuilder sb = new StringBuilder();
        sb.append((char) a).append((char) b);
        return sb.toString();
    }

    static String concatenated(int a, int b) {
        return unit(a).concat(unit(b));
    }

    static int length(int a, int b) {
        return two(a, b).length();
    }

    static int charAt(int a, int b, int i) {
        return two(a, b).charAt(i);
    }

    static String tail(int a, int b) {
        return two(a, b).substring(1);
    }

    static String head(int a, int b) {
        return two(a, b).substring(0, 1);
    }

    static boolean same(int a, int b) {
        return unit(a).equals(unit(b));
    }

    static int hash(int a) {
        return unit(a).hashCode();
    }

    static int compare(int a, int b) {
        return unit(a).compareTo(unit(b));
    }

    static boolean starts(int a, int b, int c) {
        return two(a, b).startsWith(unit(c));
    }

    static boolean ends(int a, int b, int c) {
        return two(a, b).endsWith(unit(c));
    }

    static int indexOf(int a, int b, int c) {
        return two(a, b).indexOf(unit(c));
    }

    static boolean contains(int a, int b, int c) {
        return two(a, b).contains(unit(c));
    }

    static String replaced(int a, int b, int c) {
        return two(a, b).replace((char) a, (char) c);
    }

    static int builtLength(int a, int b) {
        StringBuilder sb = new StringBuilder();
        sb.append((char) a).append((char) b);
        return sb.length();
    }

    static int builtCharAt(int a, int b, int i) {
        StringBuilder sb = new StringBuilder();
        sb.append((char) a).append((char) b);
        return sb.charAt(i);
    }

    static boolean empty(int a) {
        return (a == 0 ? "" : unit(a)).isEmpty();
    }

    static String upper(int a) {
        return unit(a).toUpperCase();
    }

    static String stripped(int a, int b) {
        return (unit(a) + "x" + unit(b)).strip();
    }

    static String trimmed(int a, int b) {
        return (unit(a) + "x" + unit(b)).trim();
    }

    static boolean blank(int a, int b) {
        return two(a, b).isBlank();
    }

    static String reversed(int a, int b, int c) {
        return new StringBuilder().append((char) a).append((char) b).append((char) c).reverse().toString();
    }

    static int indexOfPoint(int a, int b, int point) {
        return ("x" + two(a, b)).indexOf(point);
    }

    static int lastIndexOfPoint(int a, int b, int point) {
        return (two(a, b) + "x").lastIndexOf(point);
    }

    static int codePointAt(int a, int b, int i) {
        return two(a, b).codePointAt(i);
    }

    static String spread(int a, int b) {
        return two(a, b).replace("", "-");
    }

    static String region(int a, int b, int offset, int count) {
        return new String(new char[] {(char) a, (char) b}, offset, count);
    }

    static String inserted(int a, int b) {
        return new StringBuilder("xy").insert(1, (char) a).insert(0, unit(b)).toString();
    }

    static int parsed(int a) {
        return Integer.parseInt(unit(a));
    }

    static String charString(int a) {
        return Character.toString((char) a);
    }

    static String copied(int a) {
        return new String(unit(a));
    }
}
