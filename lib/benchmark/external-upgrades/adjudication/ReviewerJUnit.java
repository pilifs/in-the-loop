import org.junit.runner.JUnitCore;
import org.junit.runner.Request;
import org.junit.runner.Result;
import org.junit.runner.notification.Failure;

public final class ReviewerJUnit {
    public static void main(String[] args) throws Exception {
        Class<?> suite = Class.forName("com.github.davidmoten.rx.jdbc.DatabaseSyncTest");
        Result result = new JUnitCore().run(Request.method(suite, args[0]));
        System.out.println("tests=" + result.getRunCount() + " skipped=" + result.getIgnoreCount()
                + " failures=" + result.getFailureCount());
        for (Failure failure : result.getFailures()) {
            System.out.println(failure.getDescription().getMethodName() + " -> "
                    + failure.getException().getClass().getName() + " " + failure.getMessage());
        }
        if (!result.wasSuccessful()) System.exit(1);
    }
}
