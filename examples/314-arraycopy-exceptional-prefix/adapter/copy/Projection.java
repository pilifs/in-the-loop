package copy;

public final class Projection {
    public static boolean assignable(int code) {
        while (code != 0) {
            code--;
            if (code % 3 == 2) return false;
            code /= 3;
        }
        return true;
    }

    private static Object[] input(int code) {
        int length = code == 0 ? 0 : code <= 3 ? 1 : code <= 12 ? 2 : 3;
        Object[] source = new Object[length];
        for (int i = 0; i < length; i++) {
            code--;
            int digit = code % 3;
            source[i] = digit == 0 ? null : digit == 1 ? "A" : Integer.valueOf(1);
            code /= 3;
        }
        return source;
    }

    private static String[] destination(int length) {
        String[] array = new String[length];
        for (int i = 0; i < length; i++) array[i] = "x";
        return array;
    }

    public static int thrown(int code) {
        Object[] source = input(code);
        try {
            Copy.transfer(source, destination(source.length));
            return 0;
        } catch (ArrayStoreException expected) {
            return 1;
        }
    }

    public static int state(int code) {
        Object[] source = input(code);
        String[] destination = destination(source.length);
        try {
            Copy.transfer(source, destination);
        } catch (ArrayStoreException expected) {
            // The caller can still inspect the destination.
        }
        int result = 0;
        for (String value : destination) {
            result = 3 * result + (value == null ? 1 : "A".equals(value) ? 2 : 0);
        }
        return result;
    }
}
