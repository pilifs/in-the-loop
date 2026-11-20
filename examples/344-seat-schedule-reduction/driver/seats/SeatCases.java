package seats;

import java.util.Arrays;

public final class SeatCases {
    public static void main(String[] args) throws Exception {
        for (int code=0; code<36; code++) {
            Reservations.Result r = Reservations.execute(code);
            System.out.printf("{\"id\":%d,\"ack\":%s,\"owners\":%s,\"logs\":%s,\"invoked\":%s,\"returned\":%s}%n",
                    code,Arrays.deepToString(r.acknowledgement),Arrays.toString(r.owners),Arrays.deepToString(r.logs),
                    Arrays.deepToString(r.invoked),Arrays.deepToString(r.returned));
        }
    }
}
