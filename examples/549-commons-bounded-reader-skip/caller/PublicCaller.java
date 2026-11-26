import org.apache.commons.io.input.BoundedReader;

import java.io.*;

public class PublicCaller {
    static String next(Reader r) throws IOException {
        int c = r.read();
        return c < 0 ? "-1" : String.valueOf((char) c);
    }

    static String shortSkip(int request) throws Exception {
        var limited =
                new FilterReader(new StringReader("012345")) {
                    public long skip(long n) throws IOException {
                        return super.skip(Math.min(n, 1));
                    }
                };
        try (var wrapper = new BoundedReader(limited, 3)) {
            return wrapper.skip(request)
                    + "/"
                    + next(wrapper)
                    + "/"
                    + next(wrapper)
                    + "/"
                    + next(wrapper);
        }
    }

    public static String observe(String[] a) throws Exception {
        if (a[0].equals("control")) return shortSkip(1) + ";request3=" + shortSkip(3);
        var base = new StringReader("012345");
        if (a[0].equals("intent")) {
            var w = new BoundedReader(base, 3);
            return w.skip(5) + "/" + next(w) + "/" + next(base);
        }
        var byRead = new BoundedReader(new StringReader("012345"), 5);
        byRead.mark(2);
        var bySkip = new BoundedReader(base, 5);
        bySkip.mark(2);
        return next(byRead)
                + "/"
                + next(byRead)
                + "/"
                + next(byRead)
                + ";"
                + bySkip.skip(4)
                + "/"
                + next(base);
    }
}
