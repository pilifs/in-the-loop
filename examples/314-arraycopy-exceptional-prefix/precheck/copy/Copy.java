package copy;

public final class Copy {
    public static void transfer(Object[] source, String[] destination) {
        for (Object value : source) {
            if (value != null && !(value instanceof String)) throw new ArrayStoreException();
        }
        System.arraycopy(source, 0, destination, 0, source.length);
    }
}
