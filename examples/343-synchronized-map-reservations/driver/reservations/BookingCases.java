package reservations;

import java.util.Arrays;

public final class BookingCases {
    public static void main(String[] args) throws Exception {
        for (int code=0; code<6; code++) {
            Booking.History h = Booking.run(code, true);
            String second = h.owners[1] == null ? "null" : "\"" + h.owners[1] + "\"";
            System.out.printf("{\"mode\":%d,\"distinct\":%b,\"invoked\":%s,\"returned\":%s,\"success\":%s,"
                            + "\"size\":%d,\"owners\":[\"%s\",%s]}%n",
                    code % 3, code >= 3, Arrays.toString(h.calls), Arrays.toString(h.returns),
                    Arrays.toString(h.winners), h.size, h.owners[0], second);
        }
    }
}
