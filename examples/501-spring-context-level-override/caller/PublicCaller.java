import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.platform.launcher.core.*;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;
import org.mockito.Mockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.*;
import org.springframework.test.context.*;
import org.springframework.test.context.bean.override.convention.TestBean;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.context.junit.jupiter.SpringExtension;

public class PublicCaller {
    interface Service {String greeting();}
    record Caller(Service service) {}
    interface FooService {}
    interface BarService {}
    static String result;
    static ApplicationContext firstParent;
    static boolean firstMock,firstClean;
    @Configuration(proxyBeanMethods=false) static class Parent {
        @Bean Service service() {return () -> "P";}
        @Bean Caller parentCaller(Service s) {return new Caller(s);}
    }
    @Configuration(proxyBeanMethods=false) static class Child {
        @Bean Service service() {return () -> "C";}
        @Bean Caller childCaller(Service s) {return new Caller(s);}
    }
    @ExtendWith(SpringExtension.class)
    static abstract class Levels {
        @Autowired ApplicationContext child;
        ApplicationContext parent() {return child.getParent();}
        Caller parentCaller() {return parent().getBean("parentCaller",Caller.class);}
        Caller childCaller() {return child.getBean("childCaller",Caller.class);}
        String greetings() {return parentCaller().service().greeting()+"/"+childCaller().service().greeting();}
    }
    @ContextHierarchy({@ContextConfiguration(name="parent",classes=Parent.class),@ContextConfiguration(name="child",classes=Child.class)})
    static class ChildOnly extends Levels {
        @TestBean(name="service",contextName="child",methodName="replacement") Service field;
        static Service replacement() {return () -> "X";}
        @Test void check() {
            result=greetings()+" local="+(parent().getBean("service")==parentCaller().service() && child.getBean("service")==childCaller().service())
                    +" field="+(field==childCaller().service());
        }
    }
    @ContextHierarchy({@ContextConfiguration(name="parent",classes=Parent.class),@ContextConfiguration(name="child",classes=Child.class)})
    static class All extends Levels {
        @TestBean(name="service",methodName="replacement") Service field;
        static Service replacement() {return () -> "X";}
        @Test void check() {result=greetings();}
    }
    @ContextHierarchy({@ContextConfiguration(name="parent",classes=Parent.class),@ContextConfiguration(name="child",classes=Child.class)})
    static class Split extends Levels {
        @TestBean(name="service",contextName="parent",methodName="a") Service aField;
        @TestBean(name="service",contextName="child",methodName="b") Service bField;
        static Service a() {return () -> "A";} static Service b() {return () -> "B";}
        @Test void check() {
            result=greetings()+" fields="+(aField==parentCaller().service() && bField==childCaller().service()
                    && aField==parent().getBean("service") && bField==child.getBean("service"))
                    +" parentAgain="+parent().getBean("service",Service.class).greeting();
        }
    }
    @Configuration(proxyBeanMethods=false) static class FooChild {@Bean FooService foo(){return new FooService(){};}}
    @Configuration(proxyBeanMethods=false) static class BarChild {@Bean BarService bar(){return new BarService(){};}}
    static boolean clean(ApplicationContext p) {
        return p.getBeanNamesForType(FooService.class).length==0 && p.getBeanNamesForType(BarService.class).length==0;
    }
    @ExtendWith(SpringExtension.class)
    @ContextHierarchy({@ContextConfiguration(name="parent",classes=Parent.class),@ContextConfiguration(name="child",classes=FooChild.class)})
    static class FooClient {
        @MockitoBean(contextName="child") FooService foo;
        @Autowired ApplicationContext ctx;
        @Test void check() {
            firstParent=ctx.getParent(); firstClean=clean(firstParent);
            firstMock=Mockito.mockingDetails(foo).isMock() && foo==ctx.getBean(FooService.class);
        }
    }
    @ExtendWith(SpringExtension.class)
    @ContextHierarchy({@ContextConfiguration(name="parent",classes=Parent.class),@ContextConfiguration(name="child",classes=BarChild.class)})
    static class BarClient {
        @MockitoBean(contextName="child") BarService bar;
        @Autowired ApplicationContext ctx;
        @Test void check() {
            result="mocks="+(firstMock && Mockito.mockingDetails(bar).isMock() && bar==ctx.getBean(BarService.class))
                    +" parentReused="+(ctx.getParent()==firstParent)+" parentClean="+(firstClean && clean(ctx.getParent()));
        }
    }
    static void run(Class<?> type) {
        var request=LauncherDiscoveryRequestBuilder.request().selectors(selectClass(type)).build();
        var summary=new SummaryGeneratingListener();
        LauncherFactory.create().execute(request,summary);
        var s=summary.getSummary();
        if (s.getTestsSucceededCount()!=1 || s.getTotalFailureCount()!=0) {
            if (s.getFailures().isEmpty()) throw new AssertionError("test did not run");
            Throwable ex=s.getFailures().get(0).getException();
            while(ex.getCause()!=null) ex=ex.getCause();
            result="failed "+ex.getClass().getSimpleName()+": "+ex.getMessage();
        }
    }
    public static String observe(String[] args) {
        // A historical JVM silently ignores a new annotation member present in a caller class file.
        boolean hasSelector;
        try {TestBean.class.getMethod("contextName"); hasSelector=true;} catch(NoSuchMethodException e) {hasSelector=false;}
        if (!hasSelector && args[0].equals("child")) return "selector unavailable";
        switch(args[0]) {
            case "child" -> run(ChildOnly.class);
            case "all" -> run(All.class);
            case "split" -> run(Split.class);
            case "cache" -> {run(FooClient.class); run(BarClient.class);}
            default -> throw new IllegalArgumentException(args[0]);
        }
        return result;
    }
}
