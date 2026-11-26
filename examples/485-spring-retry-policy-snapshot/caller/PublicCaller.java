import java.io.*;
import java.time.Duration;
import org.springframework.core.retry.*;

public class PublicCaller {
    static String run(RetryPolicy p) {
        int[] calls = {0};
        try {
            int value = new RetryTemplate(p).execute(() -> {
                if (++calls[0] == 1) throw new FileNotFoundException();
                return 7;
            });
            return calls[0] + ":" + value;
        } catch (RetryException e) { return calls[0] + ":" + e.getClass().getSimpleName(); }
    }
    public static String observe(String[] args) {
        var builder = RetryPolicy.builder().maxRetries(1).delay(Duration.ZERO).includes(IOException.class);
        var a = builder.build();
        var b = builder.includes(IllegalArgumentException.class).excludes(FileNotFoundException.class).build();
        if (args[0].equals("execute")) return run(a) + " / " + run(b);
        var p = args[0].equals("old") ? a : b;
        return (p == b ? p.shouldRetry(new IOException()) + "," : "")
                + p.shouldRetry(new IllegalArgumentException()) + "," + p.shouldRetry(new FileNotFoundException());
    }
}
