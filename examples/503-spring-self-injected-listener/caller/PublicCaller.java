import java.util.*;
import org.aspectj.lang.annotation.*;
import org.springframework.context.ApplicationListener;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.event.test.self_inject.*;

public class PublicCaller {
    public static class Other implements ApplicationListener<MyEvent> {
        final List<MyEvent> events=new ArrayList<>();
        public void onApplicationEvent(MyEvent event) {events.add(event);}
    }
    @Aspect
    public static class CountAdvice {
        static final List<MyEvent> events=new ArrayList<>();
        @Before(value="execution(* org.springframework.context.event.test.self_inject.MyEventListener.onApplicationEvent(org.springframework.context.event.test.self_inject.MyEvent)) && args(event)",argNames="event")
        public void called(MyEvent event) {events.add(event);}
    }
    public static String observe(String[] args) {
        boolean plain=args[0].equals("plain"), challenge=args[0].equals("advice");
        try (var c=new AnnotationConfigApplicationContext()) {
            if (!plain) c.scan(MyApplication.class.getPackageName());
            if (plain || challenge) c.register(Other.class);
            if (challenge) c.register(CountAdvice.class);
            c.refresh();
            if (plain) {
                var a=new MyEvent(c,"first"); var b=new MyEvent(c,"second");
                c.publishEvent(a); c.publishEvent(b);
                var seen=c.getBean(Other.class).events;
                return "ordered="+(seen.size()==2 && seen.get(0)==a && seen.get(1)==b)+" count="+seen.size();
            }
            int baseline=MyEventListener.eventCount;
            var publisher=c.getBean(MyEventPublisher.class);
            publisher.publishMyEvent("first");
            int first=MyEventListener.eventCount-baseline;
            if (!challenge) return "callbacks="+first;
            var separate=c.getBean(Other.class).events;
            int firstAdvice=CountAdvice.events.size(), firstOther=separate.size();
            publisher.publishMyEvent("second");
            boolean same=separate.size()==2 && CountAdvice.events.size()==2 && separate.get(0)!=separate.get(1)
                    && separate.get(0)==CountAdvice.events.get(0) && separate.get(1)==CountAdvice.events.get(1);
            return "first="+first+"/"+firstAdvice+"/"+firstOther+" second="+(MyEventListener.eventCount-baseline-first)
                    +"/"+(CountAdvice.events.size()-firstAdvice)+"/"+(separate.size()-firstOther)+" identities="+same;
        }
    }
}
