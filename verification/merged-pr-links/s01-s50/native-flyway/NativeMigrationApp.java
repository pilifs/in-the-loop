package fixture.springboot;

import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.RuntimeHintsRegistrar;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.flyway.autoconfigure.FlywayAutoConfiguration;
import org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.ImportRuntimeHints;
import org.springframework.core.NativeDetector;

@Configuration(proxyBeanMethods = false)
@ImportAutoConfiguration({DataSourceAutoConfiguration.class, FlywayAutoConfiguration.class})
@ImportRuntimeHints(NativeMigrationApp.Migrations.class)
public class NativeMigrationApp {
    public static class Migrations implements RuntimeHintsRegistrar {
        @Override
        public void registerHints(RuntimeHints hints, ClassLoader loader) {
            hints.resources().registerPattern("db/migration");
            hints.resources().registerPattern("db/migration/**");
        }
    }

    public static void main(String[] args) throws Exception {
        var app = new SpringApplication(NativeMigrationApp.class);
        app.setWebApplicationType(WebApplicationType.NONE);
        try (var context = app.run(args)) {
            MigrationInfo[] applied = context.getBean(Flyway.class).info().applied();
            if (applied.length != 1) throw new IllegalStateException("applied migrations: " + applied.length);
            try (var connection = context.getBean(DataSource.class).getConnection();
                 var statement = connection.createStatement();
                 var rows = statement.executeQuery("select marker from fixture_users")) {
                if (!rows.next()) throw new IllegalStateException("no marker");
                int marker = rows.getInt(1);
                if (rows.next()) throw new IllegalStateException("duplicate marker");
                System.out.println("MIGRATION runtime=" + (NativeDetector.inNativeImage() ? "native" : "jvm")
                        + " version=" + applied[0].getVersion() + " checksum=" + applied[0].getChecksum()
                        + " row=" + marker);
            }
        }
    }
}
