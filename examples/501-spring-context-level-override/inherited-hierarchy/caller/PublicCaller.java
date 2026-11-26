import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.ContextHierarchy;
import org.springframework.test.context.bean.override.convention.TestBean;
import org.springframework.test.context.junit.jupiter.SpringExtension;

public class PublicCaller {
    public record Service(String value) {}
    public record Client(Service service) {}
    static String readback;

    @Configuration(proxyBeanMethods=false)
    static class Parent {
        @Bean Service service() {return new Service("P");}
        @Bean Client parentClient(Service service) {return new Client(service);}
    }

    @Configuration(proxyBeanMethods=false)
    static class Child {
        @Bean Service service() {return new Service("C");}
        @Bean Client childClient(Service service) {return new Client(service);}
    }

    @ExtendWith(SpringExtension.class)
    static abstract class Reader {
        @Autowired ApplicationContext context;
        static Service replacement() {return new Service("X");}

        void read(Service field) {
            var parent = context.getParent();
            var a = parent.getBean("parentClient", Client.class).service();
            var b = context.getBean("childClient", Client.class).service();
            if (a != parent.getBean("service") || b != context.getBean("service"))
                throw new AssertionError("caller and level-local lookup disagree");
            readback = a.value() + "/" + b.value() + (field == null ? "" : " fieldIsChild=" + (field == b));
        }
    }

    @ContextHierarchy({@ContextConfiguration(name="parent", classes=Parent.class),
                       @ContextConfiguration(name="child", classes=Child.class)})
    static abstract class Inherited extends Reader {}

    static class InheritedPlain extends Inherited {
        @Test void inspect() {read(null);}
    }

    static class InheritedAll extends Inherited {
        @TestBean(name="service", methodName="replacement") Service field;
        @Test void inspect() {read(field);}
    }

    static class InheritedChild extends Inherited {
        @TestBean(name="service", contextName="child", methodName="replacement") Service field;
        @Test void inspect() {read(field);}
    }

    @ContextHierarchy({@ContextConfiguration(name="parent", classes=Parent.class),
                       @ContextConfiguration(name="child", classes=Child.class)})
    static class DirectAll extends Reader {
        @TestBean(name="service", methodName="replacement") Service field;
        @Test void inspect() {read(field);}
    }

    @ContextHierarchy({@ContextConfiguration(name="parent", classes=Parent.class),
                       @ContextConfiguration(name="child", classes=Child.class)})
    static class DirectChild extends Reader {
        @TestBean(name="service", contextName="child", methodName="replacement") Service field;
        @Test void inspect() {read(field);}
    }

    static String run(Class<?> type) {
        var request = LauncherDiscoveryRequestBuilder.request().selectors(selectClass(type)).build();
        var listener = new SummaryGeneratingListener();
        LauncherFactory.create().execute(request, listener);
        var summary = listener.getSummary();
        if (summary.getTestsSucceededCount() == 1 && summary.getTotalFailureCount() == 0) return readback;
        if (summary.getTotalFailureCount() != 1 || readback != null) throw new AssertionError("unexpected Jupiter result");
        var error = summary.getFailures().get(0).getException();
        while (error.getCause() != null) error = error.getCause();
        String message = String.valueOf(error.getMessage());
        if (message.contains("internalBeanOverrideRegistry")) return error.getClass().getSimpleName() + ": registry missing";
        if (message.contains("no BeanOverrideHandler has been registered")) return error.getClass().getSimpleName() + ": no override handler";
        return error.getClass().getSimpleName() + ": " + message;
    }

    public static String observe(String[] args) {
        return switch (args[0]) {
            case "plain" -> run(InheritedPlain.class);
            case "direct-all" -> run(DirectAll.class);
            case "direct-child" -> run(DirectChild.class);
            case "inherited-all" -> run(InheritedAll.class);
            case "inherited-child" -> run(InheritedChild.class);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
