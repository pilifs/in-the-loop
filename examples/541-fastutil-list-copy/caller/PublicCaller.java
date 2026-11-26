import it.unimi.dsi.fastutil.ints.IntImmutableList;

import java.util.*;

public class PublicCaller {
    static String copy(int length, int pad) {
        var list = IntImmutableList.of(0, 1, 2, 3);
        int[] dest = new int[length];
        Arrays.fill(dest, pad);
        int[] got = list.toArray(dest);
        String result = (got == dest) + "/" + Arrays.toString(got) + "/";
        if (length < 4) return result + Arrays.toString(dest);
        dest[0] = 99;
        return result + list.getInt(0);
    }

    public static String observe(String[] a) {
        return switch (a[0]) {
            case "control" -> copy(2, 77);
            case "challenge" -> copy(5, 77) + " / " + copy(7, 88);
            default -> copy(5, 77);
        };
    }
}
