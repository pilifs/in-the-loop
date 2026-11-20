package tickets;

import java.util.Arrays;

public final class TicketCases {
    public static void main(String[] args) throws Exception {
        for (int mode = 0; mode < 3; mode++) {
            Projection.History h = Projection.history(mode, true);
            System.out.printf("{\"mode\":%d,\"invoked\":%s,\"returned\":%s,\"tickets\":%s,\"final\":%d}%n",
                    mode, Arrays.toString(h.calls), Arrays.toString(h.returns), Arrays.toString(h.values), h.state);
        }
    }
}
