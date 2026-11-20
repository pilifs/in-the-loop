package seats;
public final class Handles {
    public static Seat second(Seat first, boolean alias) { return alias ? first : new Seat(); }
}
