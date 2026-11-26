import org.springframework.beans.factory.NoUniqueBeanDefinitionException;
import org.springframework.context.annotation.*;
import org.springframework.context.support.GenericApplicationContext;

public class PublicCaller {
    public interface Service {}
    public static class Regular implements Service {}
    public static class Reserve implements Service {}
    static String lookup(GenericApplicationContext c) {
        try {
            Service selected=c.getBean(Service.class);
            return selected==c.getBean("regular") ? "regular" : selected==c.getBean("reserve") ? "reserve" : "other";
        } catch (NoUniqueBeanDefinitionException e) {return e.getClass().getSimpleName();}
    }
    static String exercise(String mode, boolean reverse) {
        try (var c=new GenericApplicationContext()) {
            var r=new AnnotatedBeanDefinitionReader(c);
            if (reverse) r.registerBean(Regular.class,"regular");
            r.registerBean(Reserve.class,"reserve",mode.equals("primary") ? Primary.class : Fallback.class);
            if (!reverse) r.registerBean(Regular.class,"regular");
            c.refresh();
            if (!mode.equals("stream")) return lookup(c);
            var all=c.getBeanProvider(Service.class).stream().toList();
            boolean both=all.size()==2 && all.stream().filter(s -> s==c.getBean("regular")).count()==1
                    && all.stream().filter(s -> s==c.getBean("reserve")).count()==1;
            return "both=" + both + " single=" + lookup(c);
        }
    }
    public static String observe(String[] args) {
        String first=exercise(args[0],false);
        return args[0].equals("stream") ? first+" / "+exercise(args[0],true) : first;
    }
}
