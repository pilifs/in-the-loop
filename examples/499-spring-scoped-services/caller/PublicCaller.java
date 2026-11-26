import org.springframework.beans.factory.NoUniqueBeanDefinitionException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.*;

public class PublicCaller {
    public interface Service {String route();}
    static class Consumer {
        final Service selected;
        Consumer(Service selected) {this.selected=selected;}
        String route() {return selected.route();}
    }
    static class ArchiveConsumer {
        final Service selected;
        ArchiveConsumer(@Qualifier("archive") Service selected) {this.selected=selected;}
    }
    static Service dispatcher(Service a,Service b) {return () -> "D("+a.route()+","+b.route()+")";}
    @Configuration(proxyBeanMethods=false)
    static class Plain {
        @Bean(defaultCandidate=false) Service legacy() {return () -> "L";}
        @Bean(defaultCandidate=false) Service current() {return () -> "C";}
        @Bean Service dispatcher(@Qualifier("legacy") Service a,@Qualifier("current") Service b) {return PublicCaller.dispatcher(a,b);}
    }
    @Configuration(proxyBeanMethods=false)
    static class Proxied {
        @Bean(defaultCandidate=false) @Scope(proxyMode=ScopedProxyMode.INTERFACES) Service legacy() {return () -> "L";}
        @Bean(defaultCandidate=false) @Scope(proxyMode=ScopedProxyMode.INTERFACES) Service current() {return () -> "C";}
        @Bean @Scope(proxyMode=ScopedProxyMode.INTERFACES)
        Service dispatcher(@Qualifier("legacy") Service a,@Qualifier("current") Service b) {return PublicCaller.dispatcher(a,b);}
    }
    @Configuration(proxyBeanMethods=false)
    static class Archive {
        @Bean(defaultCandidate=false) @Scope(proxyMode=ScopedProxyMode.INTERFACES) Service archive() {return () -> "A";}
    }
    public static String observe(String[] args) {
        try (var c=new AnnotationConfigApplicationContext()) {
            c.register(args[0].equals("plain") ? Plain.class : Proxied.class, Consumer.class);
            boolean extra=args[0].equals("extra");
            if (extra) c.register(Archive.class,ArchiveConsumer.class);
            try { c.refresh(); } catch (RuntimeException e) {
                for (Throwable t=e;t!=null;t=t.getCause()) if (t instanceof NoUniqueBeanDefinitionException) return t.getClass().getSimpleName();
                throw e;
            }
            return c.getBean(Consumer.class).route() + (extra ? " / "+c.getBean(ArchiveConsumer.class).selected.route() : "");
        }
    }
}
