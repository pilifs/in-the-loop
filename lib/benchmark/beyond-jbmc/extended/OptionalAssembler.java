import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.SpringVersion;

public final class OptionalAssembler {
    @Configuration static class ConfigPageFirst {
        @Bean PageAssemblerImpl<?> pageAssembler() { return new PageAssemblerImpl<>(); }
        @Bean Assembler<SomeType> someAssembler() { return new Assembler<SomeType>() {}; }
    }
    @Configuration static class ConfigSomeFirst {
        @Bean Assembler<SomeType> someAssembler() { return new Assembler<SomeType>() {}; }
        @Bean PageAssemblerImpl<?> pageAssembler() { return new PageAssemblerImpl<>(); }
    }
    public static class AssemblerInjection {
        @Autowired(required = false) Assembler<SomeType> assembler0;
        @Autowired(required = false) Assembler<SomeOtherType> assembler1;
        @Autowired(required = false) Assembler<Page<String>> assembler2;
        @Autowired(required = false) Assembler<Page<?>> assembler4;
    }
    interface Assembler<T> {}
    interface PageAssembler<T> extends Assembler<Page<T>> {}
    static class PageAssemblerImpl<T> implements PageAssembler<T> {}
    interface Page<T> {}
    interface SomeType {}
    interface SomeOtherType {}

    static int sites(int order) {
        Class<?> config=(order & 1)==0 ? ConfigPageFirst.class : ConfigSomeFirst.class;
        Class<?>[] registered=order<2 ? new Class<?>[]{config,AssemblerInjection.class} : new Class<?>[]{AssemblerInjection.class,config};
        try (AnnotationConfigApplicationContext ctx=new AnnotationConfigApplicationContext(registered)) {
            AssemblerInjection target=ctx.getBean(AssemblerInjection.class);
            Object page=ctx.getBean("pageAssembler"),some=ctx.getBean("someAssembler");
            if (target.assembler0!=some || target.assembler2!=page || target.assembler4!=page) return -1;
            return target.assembler1==null ? 0 : target.assembler1==page ? 1 : -2;
        }
    }
    public static boolean intended(int order) { return order<0 || order>3 || sites(order)>=0; }
    public static boolean otherAbsent(int order) { return order<0 || order>3 || sites(order)==0; }
}
