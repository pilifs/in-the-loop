package slice.driver;

import slice.adapter.SimpleMatchAdapter;

/** The runtime slice's concrete control. Each argument is one input, a JSON array of two strings or nulls
 * ({@code ["a*", "abc"]}, the oracle's PROBES as runtime passes them). It prints one JSON line per input: the input as
 * given, and the outcome as the JVM gave it (a value, or the exception's class). It decides nothing: the oracle reads
 * these lines. An argument it can't read stops it with no line for that input, an incomplete replay. */
public final class SimpleMatchDriver {
    private SimpleMatchDriver() {
    }

    public static void main(String[] args) {
        for (String arg : args) {
            String[] input = new Reader(arg).pair();
            String outcome;
            try {
                outcome = "\"returned\",\"value\":" + SimpleMatchAdapter.simpleMatch(input[0], input[1]);
            } catch (RuntimeException e) {
                outcome = "\"threw\",\"exception\":\"" + e.getClass().getName() + "\"";
            }
            System.out.println("{\"input\":" + arg + ",\"outcome\":" + outcome + "}");
        }
    }

    /** Just enough JSON for the inputs: an array of two values, each null or a string with JSON's escapes. */
    private static final class Reader {
        private final String text;
        private int at;

        Reader(String text) {
            this.text = text;
        }

        String[] pair() {
            expect('[');
            String first = value();
            expect(',');
            String second = value();
            expect(']');
            space();
            if (at != text.length()) {
                throw refuse("trailing text");
            }
            return new String[] {first, second};
        }

        private void space() {
            while (at < text.length() && " \t\n\r".indexOf(text.charAt(at)) >= 0) {
                at++;
            }
        }

        private void expect(char c) {
            space();
            if (at >= text.length() || text.charAt(at) != c) {
                throw refuse("expected '" + c + "'");
            }
            at++;
        }

        private String value() {
            space();
            if (text.startsWith("null", at)) {
                at += 4;
                return null;
            }
            expect('"');
            StringBuilder b = new StringBuilder();
            while (at < text.length()) {
                char c = text.charAt(at++);
                if (c == '"') {
                    return b.toString();
                }
                if (c != '\\') {
                    b.append(c);
                    continue;
                }
                if (at >= text.length()) {
                    break;
                }
                char e = text.charAt(at++);
                switch (e) {
                    case '"', '\\', '/' -> b.append(e);
                    case 'b' -> b.append('\b');
                    case 'f' -> b.append('\f');
                    case 'n' -> b.append('\n');
                    case 'r' -> b.append('\r');
                    case 't' -> b.append('\t');
                    case 'u' -> {
                        if (at + 4 > text.length()) {
                            throw refuse("a short \\u escape");
                        }
                        b.append((char) Integer.parseInt(text.substring(at, at + 4), 16));
                        at += 4;
                    }
                    default -> throw refuse("an unknown escape \\" + e);
                }
            }
            throw refuse("an unterminated string");
        }

        private IllegalArgumentException refuse(String why) {
            return new IllegalArgumentException("input " + text + ": " + why + " at " + at);
        }
    }
}
