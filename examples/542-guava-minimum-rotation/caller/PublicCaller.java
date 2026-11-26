import com.google.common.primitives.Ints;

import java.util.*;

public class PublicCaller {
    static String rotate(int distance) {
        int[] a = {1, 2, 3};
        List<Integer> ref = new ArrayList<>(List.of(1, 2, 3));
        Ints.rotate(a, distance);
        Collections.rotate(ref, distance);
        return Arrays.toString(a) + "/" + ref;
    }

    static String middle(int left, int right) {
        int[] a = {left, 1, 2, 3, 4, 5, right};
        var ref = new ArrayList<>(List.of(1, 2, 3, 4, 5));
        Collections.rotate(ref, Integer.MIN_VALUE);
        Ints.rotate(a, Integer.MIN_VALUE, 1, 6);
        return Arrays.toString(a) + "/" + ref;
    }

    public static String observe(String[] a) {
        return a[0].equals("challenge")
                ? middle(9, 8) + " / " + middle(-7, 42)
                : rotate(a[0].equals("control") ? -1 : Integer.MIN_VALUE);
    }
}
