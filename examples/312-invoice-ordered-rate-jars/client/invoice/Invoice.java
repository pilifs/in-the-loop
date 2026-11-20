package invoice;

public final class Invoice {
    public static int total(int q) {
        return q * Rate.value();
    }
}
