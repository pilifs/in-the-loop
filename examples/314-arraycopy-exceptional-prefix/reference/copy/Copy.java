package copy;

public final class Copy {
    public static void transfer(Object[] source, String[] destination) {
        System.arraycopy(source, 0, destination, 0, source.length);
    }
}
