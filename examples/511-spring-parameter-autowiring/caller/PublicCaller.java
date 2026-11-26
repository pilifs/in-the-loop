import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.platform.launcher.core.*;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.springframework.beans.factory.annotation.*;
import org.springframework.beans.factory.support.AutowireUtils;
import org.springframework.context.annotation.*;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.junit.jupiter.SpringExtension;

import java.lang.reflect.Parameter;

public class PublicCaller {
    static class Marker {}

    static class West extends Marker {}

    static class East extends Marker {}

    @Configuration
    public static class Config {
        @Bean
        public West west() {
            return new West();
        }

        @Bean
        public East east() {
            return new East();
        }
    }

    static void method(@Qualifier("west") Marker marker) {}

    static class Base<T> {
        void accept(@Autowired T value) {}
    }

    static class WestFixture extends Base<West> {}

    static class EastFixture extends Base<East> {}

    @ExtendWith(SpringExtension.class)
    @ContextConfiguration(classes = Config.class)
    public static class Jupiter {
        static String observed;

        @Test
        void check(
                @Qualifier("west") Marker value,
                org.springframework.context.ApplicationContext context) {
            observed = value == context.getBean("west") ? "west" : "other";
        }
    }

    public static String observe(String[] args) throws Exception {
        Class.forName("org.springframework.beans.factory.support.AutowireUtils");
        if (args[0].equals("extension")) {
            var launcher = LauncherFactory.create();
            var result = new SummaryGeneratingListener();
            launcher.registerTestExecutionListeners(result);
            launcher.execute(
                    LauncherDiscoveryRequestBuilder.request()
                            .selectors(selectClass(Jupiter.class))
                            .build());
            if (result.getSummary().getTestsSucceededCount() != 1)
                throw new AssertionError(result.getSummary().getFailures().toString());
            return Jupiter.observed;
        }
        try (var context = new AnnotationConfigApplicationContext(Config.class)) {
            var factory = context.getAutowireCapableBeanFactory();
            Parameter param =
                    PublicCaller.class.getDeclaredMethod("method", Marker.class).getParameters()[0];
            try {
                boolean accepted = AutowireUtils.isAutowirable(param, 0);
                if (args[0].equals("qualified"))
                    return accepted
                            + "/"
                            + (AutowireUtils.resolveDependency(
                                                    param, 0, PublicCaller.class, factory)
                                            == context.getBean("west")
                                    ? "west"
                                    : "other");
                param = Base.class.getDeclaredMethod("accept", Object.class).getParameters()[0];
                Object w = AutowireUtils.resolveDependency(param, 0, WestFixture.class, factory);
                Object e = AutowireUtils.resolveDependency(param, 0, EastFixture.class, factory);
                return (w == context.getBean("west") ? "west" : "other")
                        + "/"
                        + (e == context.getBean("east") ? "east" : "other");
            } catch (NoSuchMethodError | IllegalAccessError unavailable) {
                return "inaccessible";
            }
        }
    }
}
