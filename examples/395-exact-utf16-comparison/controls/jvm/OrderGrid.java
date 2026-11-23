import java.util.ArrayList;
import java.util.List;

public final class OrderGrid {
    public static void main(String[] args) {
        char[] alphabet = {0, 1, 'A', 0xd7ff, 0xd800, 0xd802, 0xdc00, 0xffff};
        List<String> strings = new ArrayList<>();
        strings.add("");
        for (char a : alphabet) {
            strings.add(String.valueOf(a));
            for (char b : alphabet) strings.add(new String(new char[]{a, b}));
        }
        int signs = 0, ties = 0;
        for (String a : strings) for (String text : strings) {
            String b = new String(text.toCharArray());
            if (!ExactOrder.commons(a,b) || !ExactOrder.direct(a,b) || !ExactOrder.guava(a,b)
                || !ExactOrder.firstOnTie(a,b) || !ExactOrder.sameReference(a)) throw new AssertionError();
            if (!ExactOrder.onlySign(a,b)) signs++;
            if (!ExactOrder.secondOnTie(a,b)) ties++;
        }
        if (signs != 4756 || ties != 73) throw new AssertionError(signs + "/" + ties);
        System.out.println("5329 pairs, 4756 sign-normalization failures, 73 distinct equal-string ties");
    }
}
