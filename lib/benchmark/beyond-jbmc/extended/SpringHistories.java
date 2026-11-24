import java.lang.annotation.*;
import java.lang.reflect.Method;
import java.util.List;
import org.springframework.context.PayloadApplicationEvent;
import org.springframework.context.event.ApplicationListenerMethodAdapter;
import org.springframework.context.event.EventListener;
import org.springframework.core.BridgeMethodResolver;
import org.springframework.core.ResolvableType;
import org.springframework.core.annotation.*;
import org.springframework.core.convert.ConverterNotFoundException;
import org.springframework.core.convert.converter.Converter;
import org.springframework.core.convert.support.GenericConversionService;

public final class SpringHistories {
    interface Named<T> { String name(T x); }
    static class Impl implements Named<String> {
        public String name(String s){return s;}
        public String name(Integer n){return "decoy";}
    }
    public static boolean bridge() throws Exception {
        Method entry=Impl.class.getDeclaredMethod("name",Object.class);
        Method target=Impl.class.getDeclaredMethod("name",String.class);
        Method decoy=Impl.class.getDeclaredMethod("name",Integer.class);
        Method cold=BridgeMethodResolver.findBridgedMethod(entry);
        if (!entry.isBridge() || !cold.equals(target) || !BridgeMethodResolver.findBridgedMethod(decoy).equals(decoy)) return false;
        Method warm=BridgeMethodResolver.findBridgedMethod(entry);
        return warm.equals(cold) && warm.getDeclaringClass()==Impl.class && warm.getParameterTypes()[0]==String.class && !warm.isBridge();
    }
    @Retention(RetentionPolicy.RUNTIME) @Target({ElementType.TYPE,ElementType.ANNOTATION_TYPE})
    @interface Base {
        @AliasFor("path") String value() default "";
        @AliasFor("value") String path() default "";
    }
    @Retention(RetentionPolicy.RUNTIME) @Target(ElementType.TYPE) @Base
    @interface Composed { @AliasFor(annotation=Base.class,attribute="path") String name() default ""; }
    @Composed(name="x") static class Tagged {}
    @Base(value="a",path="b") static class Unequal {}
    public static boolean aliases() {
        Base m=AnnotatedElementUtils.findMergedAnnotation(Tagged.class,Base.class);
        if (m==null || !m.value().equals("x") || !m.path().equals("x") || Tagged.class.getAnnotation(Base.class)!=null) return false;
        try { AnnotatedElementUtils.findMergedAnnotation(Unequal.class,Base.class); return false; }
        catch (AnnotationConfigurationException expected) { return expected.getClass()==AnnotationConfigurationException.class; }
    }
    static final class PlusOne implements Converter<String,Integer> { public Integer convert(String s){return Integer.parseInt(s)+1;} }
    static final class PlusTwo implements Converter<String,Integer> { public Integer convert(String s){return Integer.parseInt(s)+2;} }
    static boolean empty(GenericConversionService service) {
        if(service.canConvert(String.class,Integer.class)) return false;
        try { service.convert("41",Integer.class); return false; }
        catch (ConverterNotFoundException e) { return true; }
    }
    public static boolean conversion() {
        GenericConversionService a=new GenericConversionService(),b=new GenericConversionService();
        if (!empty(a) || !empty(b)) return false;
        a.addConverter(new PlusOne());
        if (!a.canConvert(String.class,Integer.class) || a.convert("41",Integer.class)!=42 || !empty(b)) return false;
        a.addConverter(new PlusTwo());
        if (a.convert("41",Integer.class)!=43 || !empty(b)) return false;
        a.removeConvertible(String.class,Integer.class);
        if (!empty(a) || !empty(b)) return false;
        a.addConverter(new PlusOne());
        return a.convert("41",Integer.class)==42 && empty(b);
    }
    public static class Holder<T> { public List<T> listOfT; public T t; public List<String> listOfString; public String string; }
    public static class Listeners {
        @EventListener public void onString(String s){}
        @EventListener public void onList(List<String> s){}
    }
    public static boolean listener(boolean list) throws Exception {
        Method m=Listeners.class.getMethod(list?"onList":"onString",list?List.class:String.class);
        ApplicationListenerMethodAdapter a=new ApplicationListenerMethodAdapter("listeners",Listeners.class,m);
        String[] fields={"listOfT","t","listOfString","string"};
        int mask=0;
        for(int i=0;i<4;i++){
            ResolvableType t=ResolvableType.forClassWithGenerics(PayloadApplicationEvent.class,ResolvableType.forField(Holder.class.getField(fields[i])));
            if (a.supportsEventType(t)) mask|=1<<i;
        }
        return mask==(list?6:10);
    }
}
