import org.apache.commons.io.input.CharacterFilterReader;

import java.io.*;

public class PublicCaller {
    static String skip(Reader r) throws IOException {
        long n = r.skip(1);
        return n + "/" + (char) r.read() + "/" + r.read();
    }

    public static String observe(String[] a) throws Exception {
        switch (a[0]) {
            case "control":
                try (var r = new CharacterFilterReader(new StringReader("abc"), 'x')) {
                    return r.skip(1)
                            + "/"
                            + (char) r.read()
                            + "/"
                            + (char) r.read()
                            + "/"
                            + r.read();
                }
            case "challenge":
                return skip(new CharacterFilterReader(new StringReader("xaxb"), 'x'))
                        + " / "
                        + skip(new CharacterFilterReader(new StringReader("xxxxaxb"), 'x'))
                        + " / "
                        + skip(new StringReader("ab"));
            default:
                try (var r = new CharacterFilterReader(new StringReader("xxa"), 'x')) {
                    char[] buf = {'?', '?'};
                    int n = r.read(buf, 0, 2);
                    return "first="
                            + n
                            + ":"
                            + new String(buf, 0, Math.max(0, n))
                            + ",next="
                            + r.read(buf, 0, 2);
                }
        }
    }
}
