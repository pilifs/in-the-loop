import java.io.UnsupportedEncodingException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.SplittableRandom;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.IntStream;

/** What one JDK does with the two conversions example 307's revisions differ by, and with the mutant's: a record
 * for a model of {@code String.getBytes("UTF-8")}, never a proof about Strings it did not try.
 *
 * <p>For each String it tries, three byte arrays must be the same: {@code s.getBytes("UTF-8")} (revision before),
 * {@code s.getBytes(StandardCharsets.UTF_8)} (revision after), and {@link #utf8}, the encoding written out here
 * from the definition the verifier's model states (lib/src/bmc/bytes.rs): the two overloads reach one
 * implementation in OpenJDK, so they are not independent of each other, and the third is. The same Strings are
 * encoded with US-ASCII and compared with {@link #ascii}, the mutant's conversion (controls/us-ascii.patch).
 *
 * <p>The Strings: every String of one UTF-16 code unit (65,536); every String of two (4,294,967,296), which is every
 * context a unit's encoding depends on, since a surrogate is paired with one neighbour only; every String of
 * three, four and five units over {@link #CLASSES}; for every length up to {@code LONGEST}, a run of each class's
 * unit, and that run with each of the surrogate shapes put at every position; and {@code RANDOM} Strings of random
 * length up to {@code LONGEST} from a fixed seed, their units drawn by class. Lengths past 80 are there because
 * the JDK's encoder has paths that depend on the length (a compact Latin-1 String, loops over several units at a
 * time).
 *
 * <p>Also recorded, each a single call: a null String, the charset names a mutant could use (aliases of UTF-8 are
 * the same conversion; other charsets, an unknown name and a null name are not), and whether the Charset the name
 * resolves to is the object {@code StandardCharsets.UTF_8}.
 *
 * <p>Output: one JSON object on standard output, with the runtime's identity as its system properties give it.
 * The caller (run.py) adds the hash of the runtime image. Exit 0 when nothing differed. */
public final class ConversionDifferential {
    static final int LONGEST = 200;
    static final int RANDOM = 4_000_000;
    /** One unit of each class the encodings tell apart, with the units at each class's edges. */
    static final char[] CLASSES = {0x0000, 0x0001, 'a', '?', 0x007F, 0x0080, 0x00E9, 0x00FF, 0x0100, 0x07FF, 0x0800, 0x20AC, 0xD7FF, 0xD800, 0xDBFF,
        0xDC00, 0xDFFF, 0xE000, 0xFFFD, 0xFFFE, 0xFFFF};
    /** A lone high surrogate, a lone low one, a pair, a reversed pair, two highs, two lows. */
    static final String[] SHAPES = {"\uD800", "\uDC00", "😀", "\uDE00\uD83D", "\uD800\uDBFF", "\uDC00\uDFFF", "􏿿"};

    static final AtomicLong tried = new AtomicLong();
    static final AtomicLong differed = new AtomicLong();
    static final AtomicReference<String> first = new AtomicReference<>();

    /** UTF-8 as the model states it: one byte below 0x80, two below 0x800, four for a high surrogate followed by a
     * low one, the one byte '?' for a surrogate in no such pair, three otherwise. */
    static byte[] utf8(String s) {
        byte[] out = new byte[3 * s.length()];
        int n = 0;
        for (int i = 0; i < s.length(); i++) {
            int c = s.charAt(i);
            if (c < 0x80) {
                out[n++] = (byte) c;
            } else if (c < 0x800) {
                out[n++] = (byte) (0xC0 | c >> 6);
                out[n++] = (byte) (0x80 | c & 0x3F);
            } else if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length() && s.charAt(i + 1) >= 0xDC00 && s.charAt(i + 1) <= 0xDFFF) {
                int point = 0x10000 + ((c - 0xD800) << 10) + (s.charAt(++i) - 0xDC00);
                out[n++] = (byte) (0xF0 | point >> 18);
                out[n++] = (byte) (0x80 | point >> 12 & 0x3F);
                out[n++] = (byte) (0x80 | point >> 6 & 0x3F);
                out[n++] = (byte) (0x80 | point & 0x3F);
            } else if (c >= 0xD800 && c <= 0xDFFF) {
                out[n++] = '?';
            } else {
                out[n++] = (byte) (0xE0 | c >> 12);
                out[n++] = (byte) (0x80 | c >> 6 & 0x3F);
                out[n++] = (byte) (0x80 | c & 0x3F);
            }
        }
        return Arrays.copyOf(out, n);
    }

    /** US-ASCII as the JDK encodes it: a unit below 0x80 is itself; anything else is one '?', and a high surrogate
     * followed by a low one is one '?' for the two. */
    static byte[] ascii(String s) {
        byte[] out = new byte[s.length()];
        int n = 0;
        for (int i = 0; i < s.length(); i++) {
            int c = s.charAt(i);
            if (c < 0x80) {
                out[n++] = (byte) c;
            } else {
                if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length() && s.charAt(i + 1) >= 0xDC00 && s.charAt(i + 1) <= 0xDFFF) {
                    i++;
                }
                out[n++] = '?';
            }
        }
        return Arrays.copyOf(out, n);
    }

    static String units(String s) {
        StringBuilder b = new StringBuilder("u");
        for (int i = 0; i < s.length(); i++) {
            b.append(i == 0 ? "" : ",").append(Integer.toHexString(s.charAt(i)));
        }
        return b.toString();
    }

    static void check(String s) {
        tried.incrementAndGet();
        byte[] named;
        try {
            named = s.getBytes("UTF-8");
        } catch (UnsupportedEncodingException e) {
            throw new AssertionError(e);
        }
        byte[] constant = s.getBytes(StandardCharsets.UTF_8);
        boolean same = Arrays.equals(named, constant) && Arrays.equals(named, utf8(s)) && named != constant
            && Arrays.equals(s.getBytes(StandardCharsets.US_ASCII), ascii(s));
        if (!same) {
            differed.incrementAndGet();
            first.compareAndSet(null, units(s));
        }
    }

    static String outcome(String s, String name) {
        try {
            byte[] b = s.getBytes(name);
            return Arrays.equals(b, s.getBytes(StandardCharsets.UTF_8)) ? "the bytes of UTF_8" : "other bytes";
        } catch (Exception e) {
            return e.getClass().getName();
        }
    }

    static String quote(String s) {
        return s == null ? "null" : "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    public static void main(String[] args) throws Exception {
        List<String> counts = new ArrayList<>();
        long before = 0;
        // One unit, and two: every context.
        IntStream.range(0, 0x10000).forEach(a -> check(String.valueOf((char) a)));
        counts.add("\"oneUnit\":" + (tried.get() - before));
        before = tried.get();
        boolean pairs = !Arrays.asList(args).contains("--no-pairs");
        if (pairs) {
            IntStream.range(0, 0x10000).parallel().forEach(a -> {
                char[] two = {(char) a, 0};
                for (int b = 0; b < 0x10000; b++) {
                    two[1] = (char) b;
                    check(new String(two));
                }
            });
        }
        counts.add("\"twoUnits\":" + (tried.get() - before));
        before = tried.get();
        // Three to five units over the classes.
        for (int n = 3; n <= 5; n++) {
            int total = 1;
            for (int k = 0; k < n; k++) {
                total *= CLASSES.length;
            }
            char[] buffer = new char[n];
            for (int code = 0; code < total; code++) {
                for (int k = 0, rest = code; k < n; k++, rest /= CLASSES.length) {
                    buffer[k] = CLASSES[rest % CLASSES.length];
                }
                check(new String(buffer));
            }
        }
        counts.add("\"threeToFiveUnitsOverClasses\":" + (tried.get() - before));
        before = tried.get();
        // Runs of one unit at every length, and each surrogate shape at every position of each.
        check("");
        for (int n = 1; n <= LONGEST; n++) {
            for (char c : CLASSES) {
                char[] run = new char[n];
                Arrays.fill(run, c);
                String s = new String(run);
                check(s);
                for (String shape : SHAPES) {
                    for (int at = 0; at <= n; at++) {
                        check(s.substring(0, at) + shape + s.substring(at));
                    }
                }
            }
        }
        counts.add("\"runsWithSurrogateShapes\":" + (tried.get() - before));
        before = tried.get();
        // Random Strings, units by class: half from the classes' own units, half anywhere in a class's range.
        SplittableRandom random = new SplittableRandom(307);
        int[][] ranges = {{0, 0x80}, {0x80, 0x800}, {0x800, 0xD800}, {0xD800, 0xDC00}, {0xDC00, 0xE000}, {0xE000, 0x10000}};
        for (int k = 0; k < RANDOM; k++) {
            char[] buffer = new char[random.nextInt(LONGEST + 1)];
            boolean latin = random.nextInt(8) == 0;
            for (int i = 0; i < buffer.length; i++) {
                if (latin) {
                    buffer[i] = (char) random.nextInt(0x100);
                } else if (random.nextBoolean()) {
                    buffer[i] = CLASSES[random.nextInt(CLASSES.length)];
                } else {
                    int[] range = ranges[random.nextInt(ranges.length)];
                    buffer[i] = (char) random.nextInt(range[0], range[1]);
                }
            }
            check(new String(buffer));
        }
        counts.add("\"random\":" + (tried.get() - before));

        // Single calls.
        String probe = "aé€😀\uD800";
        List<String> names = new ArrayList<>();
        for (String name : new String[] {"UTF-8", "UTF8", "utf-8", "unicode-1-1-utf-8", "US-ASCII", "ISO-8859-1", "UTF-16", "no-such-charset", "", null}) {
            String resolved;
            try {
                resolved = Charset.forName(name) == StandardCharsets.UTF_8 ? "the object StandardCharsets.UTF_8" : "another Charset";
            } catch (Exception e) {
                resolved = e.getClass().getName();
            }
            names.add("{\"name\":" + quote(name) + ",\"getBytes\":" + quote(outcome(probe, name)) + ",\"forName\":" + quote(resolved) + "}");
        }
        String nullNamed;
        String nullConstant;
        try {
            ((String) null).getBytes("UTF-8");
            nullNamed = "returned";
        } catch (Exception e) {
            nullNamed = e.getClass().getName();
        }
        try {
            ((String) null).getBytes(StandardCharsets.UTF_8);
            nullConstant = "returned";
        } catch (Exception e) {
            nullConstant = e.getClass().getName();
        }
        StringBuilder out = new StringBuilder("{");
        for (String p : new String[] {"java.version", "java.runtime.version", "java.vm.version", "java.vendor", "java.vm.name", "os.arch", "file.encoding",
            "native.encoding", "sun.jnu.encoding"}) {
            out.append(quote(p)).append(":").append(quote(System.getProperty(p))).append(",");
        }
        out.append("\"defaultCharset\":").append(quote(Charset.defaultCharset().name())).append(",");
        out.append("\"longest\":").append(LONGEST).append(",\"seed\":307,");
        out.append("\"tried\":{").append(String.join(",", counts)).append(",\"total\":").append(tried.get()).append("},");
        out.append("\"differed\":").append(differed.get()).append(",\"firstDifference\":").append(quote(first.get())).append(",");
        out.append("\"nullString\":{\"getBytes(String)\":").append(quote(nullNamed)).append(",\"getBytes(Charset)\":").append(quote(nullConstant)).append("},");
        out.append("\"names\":[").append(String.join(",", names)).append("]}");
        System.out.println(out);
        System.exit(differed.get() == 0 ? 0 : 1);
    }
}
