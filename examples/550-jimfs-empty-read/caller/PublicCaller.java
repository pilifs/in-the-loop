import com.google.common.jimfs.*;

import java.io.*;
import java.nio.file.*;
import java.util.*;

public class PublicCaller {
    public static String observe(String[] a) throws Exception {
        try (var fs = Jimfs.newFileSystem(Configuration.unix())) {
            Path f = fs.getPath("/data");
            Files.write(f, a[0].equals("challenge") ? new byte[0] : new byte[] {1, 2, 3});
            byte[] dst = new byte[8];
            Arrays.fill(dst, (byte) 77);
            byte[] unchanged = dst.clone();
            try (var in = Files.newInputStream(f)) {
                if (a[0].equals("control"))
                    return in.read(dst, 2, 0)
                            + "/"
                            + Arrays.equals(dst, unchanged)
                            + "/"
                            + in.read();
                if (a[0].equals("challenge")) {
                    if (in.read() != -1) throw new AssertionError("empty file");
                    return in.read(dst, 8, 0)
                            + "/"
                            + in.read()
                            + "/"
                            + in.read(dst, 8, 0)
                            + "/"
                            + Arrays.equals(dst, unchanged);
                }
                if (!Arrays.equals(in.readNBytes(3), new byte[] {1, 2, 3}) || in.read() != -1)
                    throw new AssertionError("unconfirmed EOF");
                return in.read(dst, 2, 0) + "/" + Arrays.equals(dst, unchanged);
            }
        }
    }
}
