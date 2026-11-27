import java.util.Properties;
import org.postgresql.Driver;
import org.springframework.boot.jdbc.autoconfigure.JdbcConnectionDetails;

public class PublicCaller {
    static final String IMAGE = "postgres:17@sha256:97fb53376be3e4fb1a8a61421daa69dcc3bf2fa39bda3259f5245f9a455af1a9";
    static String read(String name) throws Exception {
        String service = "    image: " + IMAGE + "\n    environment:\n      POSTGRES_DB: '" + name
                + "'\n      POSTGRES_PASSWORD: local-fixture\n    labels:\n      org.springframework.boot.jdbc.parameters: connectTimeout=30\n"
                + "    ports:\n      - '127.0.0.1::5432/tcp'\n    healthcheck:\n"
                + "      test: ['CMD','pg_isready','-U','postgres']\n      interval: 1s\n      timeout: 2s\n      retries: 20\n";
        try (var project = new ComposeProject(service); var ctx = project.context("--spring.application.name=my-app")) {
            var details = ctx.getBean(JdbcConnectionDetails.class);
            Properties parsed = Driver.parseURL(details.getJdbcUrl(),new Properties());
            if (parsed == null) return "unparseable";
            if (Integer.parseInt(parsed.getProperty("PGPORT")) != project.port(5432,"tcp")) throw new AssertionError("unexpected database port");
            return parsed.getProperty("PGDBNAME") + "/" + parsed.getProperty("connectTimeout") + "/" + parsed.getProperty("ApplicationName");
        }
    }
    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "intent" -> read("my+db");
            case "control" -> read("database");
            case "challenge" -> read("my+db") + ";" + read("my%2Bdb");
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
