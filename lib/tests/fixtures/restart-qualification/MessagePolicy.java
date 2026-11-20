import java.lang.management.ManagementFactory;
import com.sun.management.HotSpotDiagnosticMXBean;

/** Exercise Controls.message itself and independently inspect exceptions from the same divide method. */
public final class MessagePolicy {
    public static void main(String[] args) {
        int calls = Integer.parseInt(args[0]);
        boolean fastThrow = Boolean.parseBoolean(ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class)
                .getVMOption("OmitStackTraceInFastThrow").getValue());
        int first = Controls.message(0);
        int rejected = 0;
        int firstRejection = -1;
        int exact = 0;
        int missing = 0;
        int other = 0;
        for (int i = 0; i < calls; i++) {
            int result = Controls.message(0);
            if (result == 0) {
                if (firstRejection == -1) firstRejection = i;
                rejected++;
            } else if (result != 1) {
                throw new AssertionError("unexpected policy result " + result);
            }
            try {
                Controls.divide(0);
                throw new AssertionError("division by zero returned");
            } catch (ArithmeticException e) {
                if (e.getClass() != ArithmeticException.class) throw new AssertionError(e.getClass());
                String text = e.getMessage();
                if (text == null) missing++;
                else if ("/ by zero".equals(text)) exact++;
                else other++;
            }
        }
        System.out.printf("%b %d %d %d %d %d %d%n", fastThrow, first, rejected, firstRejection, exact, missing, other);
    }
}
