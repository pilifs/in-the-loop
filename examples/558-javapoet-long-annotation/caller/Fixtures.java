package client;

import java.lang.annotation.*;

@Fixtures.Wide(12345678910L)
@Fixtures.Small(7)
@Fixtures.Many({7L, -2147483649L})
public class Fixtures {
    @Retention(RetentionPolicy.RUNTIME)
    public @interface Wide {
        long value();
    }

    @Retention(RetentionPolicy.RUNTIME)
    public @interface Small {
        int value();
    }

    @Retention(RetentionPolicy.RUNTIME)
    public @interface Many {
        long[] value();
    }
}
