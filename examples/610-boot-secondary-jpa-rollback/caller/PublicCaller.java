import java.sql.*;
import java.util.concurrent.atomic.AtomicReference;
import jakarta.persistence.EntityManagerFactory;
import com.zaxxer.hikari.HikariDataSource;
import fixture.MarkerRow;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.AutoConfigurationPackage;
import org.springframework.boot.hibernate.autoconfigure.HibernateJpaAutoConfiguration;
import org.springframework.boot.jdbc.autoconfigure.DataSourceAutoConfiguration;
import org.springframework.boot.jpa.EntityManagerFactoryBuilder;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.*;
import org.springframework.core.env.Environment;
import org.springframework.orm.jpa.persistenceunit.PersistenceManagedTypes;

public class PublicCaller {
    static HikariDataSource pool(String name, boolean autoCommit) {
        HikariDataSource ds = new HikariDataSource();
        ds.setJdbcUrl("jdbc:h2:mem:" + name);
        ds.setUsername("sa");
        ds.setAutoCommit(autoCommit);
        ds.setMaximumPoolSize(3);
        return ds;
    }
    @Configuration(proxyBeanMethods=false)
    @AutoConfigurationPackage(basePackageClasses=MarkerRow.class)
    static class Pools {
        @Bean @Primary HikariDataSource primaryPool(Environment env) {
            return pool("primary", env.getRequiredProperty("fixture.primary", Boolean.class));
        }
    }
    static void schema(HikariDataSource ds) throws SQLException {
        try (Connection c = ds.getConnection(); var s = c.createStatement()) {
            s.executeUpdate("create table if not exists proof_marker(id integer primary key)");
            if (!c.getAutoCommit()) c.commit();
        }
    }
    static int count(HikariDataSource ds, int id) throws SQLException {
        try (var c = ds.getConnection(); var s = c.prepareStatement("select count(*) from proof_marker where id=?")) {
            s.setInt(1, id);
            try (var rs = s.executeQuery()) { rs.next(); return rs.getInt(1); }
        }
    }
    static String run(boolean primaryAuto, boolean commit, int id) {
        var result = new AtomicReference<String>();
        new ApplicationContextRunner().withUserConfiguration(Pools.class)
                .withConfiguration(AutoConfigurations.of(DataSourceAutoConfiguration.class, HibernateJpaAutoConfiguration.class))
                .withPropertyValues("fixture.primary=" + primaryAuto, "spring.jpa.hibernate.ddl-auto=none").run(ctx -> {
            var primary = ctx.getBean(HikariDataSource.class);
            try (var secondary = pool("secondary", true)) {
                schema(primary);
                schema(secondary);
                var factory = ctx.getBean(EntityManagerFactoryBuilder.class).dataSource(secondary)
                        .persistenceUnit("secondary").managedTypes(PersistenceManagedTypes.of(MarkerRow.class.getName())).build();
                boolean flag = factory.getJpaPropertyMap().containsKey("hibernate.connection.provider_disables_autocommit");
                factory.afterPropertiesSet();
                try {
                    EntityManagerFactory emf = factory.getObject();
                    try (var em = emf.createEntityManager()) {
                        var tx = em.getTransaction();
                        tx.begin();
                        em.persist(new MarkerRow(id));
                        em.flush();
                        if (commit) tx.commit(); else tx.rollback();
                    }
                    result.set(count(secondary,id) + ":" + count(primary,id) + ":" + (flag ? "present" : "absent"));
                } finally { factory.destroy(); }
            }
        });
        return result.get();
    }
    public static String observe(String[] args) {
        return switch (args[0]) {
            case "intent" -> run(false, false, 17);
            case "control" -> run(false, true, 23);
            case "challenge" -> run(false, false, 31) + "/" + run(true, false, 41);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
