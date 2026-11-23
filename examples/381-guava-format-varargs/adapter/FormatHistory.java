import com.google.common.base.Strings;

public final class FormatHistory {
    public static boolean retained(boolean typed) {
        Integer a = 5, b = 6, c = 11;
        Object[] input = typed ? new Integer[]{a, b, c} : new Object[]{a, b, c};
        try {
            String text = Strings.lenientFormat("%s + %s = %s", input);
            return text.equals("5 + 6 = 11") && input[0] == a && input[1] == b && input[2] == c;
        } catch (ArrayStoreException incompatible) { return false; }
    }
    public static boolean parentBehavior(boolean typed) {
        Integer a = 5, b = 6, c = 11;
        Object[] input = typed ? new Integer[]{a, b, c} : new Object[]{a, b, c};
        try {
            String text = Strings.lenientFormat("%s + %s = %s", input);
            return !typed && text.equals("5 + 6 = 11") && "5".equals(input[0])
                    && "6".equals(input[1]) && "11".equals(input[2]);
        } catch (ArrayStoreException incompatible) {
            return typed && input[0] == a && input[1] == b && input[2] == c;
        }
    }
}
