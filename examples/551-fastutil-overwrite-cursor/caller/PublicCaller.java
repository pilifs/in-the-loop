import it.unimi.dsi.fastutil.io.FastByteArrayOutputStream;

import java.util.*;

public class PublicCaller {
    static String run(String arg, boolean singles) throws Exception {
        var out = new FastByteArrayOutputStream();
        out.write(new byte[] {1, 2, 3, 4, 5});
        if (arg.equals("control")) out.write(new byte[] {6, 7});
        else {
            out.position(0);
            if (singles) {
                for (int b : new int[] {7, 8, 9}) out.write(b);
            } else out.write(new byte[] {7, 8, 9}, 0, 3);
            if (arg.equals("challenge")) out.write(6);
        }
        return out.position()
                + "/"
                + out.length()
                + "/"
                + Arrays.toString(Arrays.copyOf(out.array, (int) out.length()));
    }

    public static String observe(String[] a) throws Exception {
        return run(a[0], false) + (a[0].equals("challenge") ? " / " + run(a[0], true) : "");
    }
}
