import java.util.*;
import org.springframework.context.annotation.*;
import org.springframework.transaction.*;
import org.springframework.transaction.annotation.*;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.transaction.support.SimpleTransactionStatus;

public class PublicCaller {
    @Transactional public static class ClassLevel {
        @TransactionalEventListener public void on(String value) {}
    }
    public static class MethodLevel {
        @Transactional @TransactionalEventListener public void required(String value) {}
        @Transactional(propagation=Propagation.REQUIRES_NEW) @TransactionalEventListener public void allowed(String value) {}
    }
    @Transactional public static class Receiver {
        static final List<String> seen=new ArrayList<>();
        @Transactional(propagation=Propagation.NOT_SUPPORTED) @TransactionalEventListener(fallbackExecution=true)
        public void on(String value) {seen.add(value);}
    }
    @Configuration(proxyBeanMethods=false) @EnableTransactionManagement
    static class Config {
        @Bean Receiver receiver() {return new Receiver();}
        @Bean PlatformTransactionManager transactionManager() {
            return new PlatformTransactionManager() {
                public TransactionStatus getTransaction(TransactionDefinition d) {
                    if(d.getPropagationBehavior()!=TransactionDefinition.PROPAGATION_NOT_SUPPORTED) throw new AssertionError(d);
                    return new SimpleTransactionStatus(false);
                }
                public void commit(TransactionStatus s) {}
                public void rollback(TransactionStatus s) {throw new AssertionError("rollback");}
            };
        }
    }
    static String create(Class<?> type,String name) throws Exception {
        var factory=new RestrictedTransactionalEventListenerFactory();
        try {return factory.createApplicationListener("listener",type,type.getMethod(name,String.class))!=null ? "accepted" : "null";}
        catch(IllegalStateException e) {return e.getClass().getSimpleName();}
    }
    public static String observe(String[] args) throws Exception {
        if(args[0].equals("class")) return create(ClassLevel.class,"on");
        if(args[0].equals("method")) return create(MethodLevel.class,"required")+"/"+create(MethodLevel.class,"allowed");
        try(var c=new AnnotationConfigApplicationContext(Config.class)) {c.publishEvent("receipt");return Receiver.seen.toString();}
    }
}
