import io.r2dbc.spi.*;

import org.springframework.r2dbc.core.DatabaseClient;

import java.time.Duration;
import java.util.*;

public class PublicCaller {
    static Integer[] read(DatabaseClient.GenericExecuteSpec query) {
        return query.map((row, metadata) -> row.get(0, Integer[].class))
                .one()
                .block(Duration.ofSeconds(8));
    }

    public static String observe(String[] args) {
        var opts =
                ConnectionFactoryOptions.builder()
                        .option(ConnectionFactoryOptions.DRIVER, "postgresql")
                        .option(ConnectionFactoryOptions.HOST, "127.0.0.1")
                        .option(
                                ConnectionFactoryOptions.PORT,
                                Integer.valueOf(System.getenv("PUBLIC_COMPARISON_PG_PORT")))
                        .option(ConnectionFactoryOptions.DATABASE, "postgres")
                        .option(ConnectionFactoryOptions.USER, "postgres")
                        .option(
                                ConnectionFactoryOptions.PASSWORD,
                                System.getenv("PUBLIC_COMPARISON_PG_PASSWORD"))
                        .build();
        DatabaseClient db = DatabaseClient.create(ConnectionFactories.get(opts));
        boolean list = args[0].equals("list");
        String literal =
                Arrays.toString(read(db.sql(list ? "SELECT ARRAY[7,2,7]" : "SELECT ARRAY[7]")));
        var query =
                db.sql(
                                args[0].equals("space")
                                        ? "SELECT CAST(ARRAY[:ext ] AS integer[])"
                                        : "SELECT CAST(ARRAY[:ext] AS integer[])")
                        .bind("ext", list ? List.of(7, 2, 7) : 7);
        try {
            return Arrays.toString(read(query)) + ":literal=" + literal;
        } catch (RuntimeException failure) {
            for (Throwable e = failure; e != null; e = e.getCause()) {
                if (e.getMessage() != null && e.getMessage().contains("ext]"))
                    return "binding failed:literal=" + literal;
            }
            throw failure;
        }
    }
}
