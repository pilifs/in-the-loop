import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.parallel.*;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.testkit.engine.EngineTestKit;
import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.*;
import org.springframework.context.annotation.Configuration;
import org.springframework.test.context.event.*;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

public class PublicCaller {
    static String mode,observation;
    static class CustomEvent extends ApplicationEvent {
        final String tag;
        CustomEvent(Object source,String tag) {super(source);this.tag=tag;}
    }
    @Configuration(proxyBeanMethods=false) static class Config {}
    @SpringJUnitConfig(Config.class) @RecordApplicationEvents
    static class Recording {
        @Autowired ApplicationEvents events;
        @Autowired ApplicationContext context;
        String read() {return events.stream(CustomEvent.class).map(e -> e.tag).toList().toString();}
        void publish(String tag) {context.publishEvent(new CustomEvent(this,tag));}
        void child(Runnable task) throws Exception {
            var failure=new AtomicReference<Throwable>();
            Thread t=new Thread(() -> {try {task.run();} catch(Throwable ex){failure.set(ex);}});
            t.start(); t.join(3000);
            if (t.isAlive()) throw new AssertionError("child still running");
            if (failure.get()!=null) throw new IllegalStateException(failure.get());
        }
        @Test void test() throws Exception {
            if (mode.equals("child")) child(() -> publish("child"));
            else if (mode.equals("parent")) publish("parent");
            else {
                publish("A"); child(() -> publish("B"));
                var second=new AtomicReference<String>();
                child(() -> {
                    try {second.set(read());} catch(RuntimeException ex){second.set(ex.getClass().getSimpleName());}
                });
                observation="child="+second+" parent="+read(); return;
            }
            observation=read();
        }
    }
    @SpringJUnitConfig(Config.class) @RecordApplicationEvents
    @TestInstance(TestInstance.Lifecycle.PER_CLASS) @Execution(ExecutionMode.CONCURRENT)
    static class Guard { @Test void test() {observation="ran";} }
    static String launch(Class<?> type,boolean parallel) {
        observation=null;
        var result=EngineTestKit.engine("junit-jupiter").selectors(selectClass(type))
                .configurationParameter("junit.jupiter.execution.parallel.enabled",String.valueOf(parallel)).execute();
        var failures=result.containerEvents().failed().list();
        if (!failures.isEmpty()) {
            Throwable error=failures.get(0).getRequiredPayload(TestExecutionResult.class).getThrowable().orElseThrow();
            if (!error.getMessage().contains("@RecordApplicationEvents")) throw new AssertionError(error);
            return error.getClass().getSimpleName();
        }
        if (result.testEvents().succeeded().count()!=1) throw new AssertionError("Jupiter test did not pass: "+result.testEvents().failed().list());
        return observation;
    }
    public static String observe(String[] args) throws Exception {
        mode=args[0];
        Class.forName("org.springframework.test.context.junit.jupiter.SpringExtension");
        if (mode.equals("guard")) return "enabled="+launch(Guard.class,true)+" disabled="+launch(Guard.class,false);
        return launch(Recording.class,false);
    }
}
