import org.springframework.context.annotation.*;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;

import java.util.*;

public class PublicCaller {
    static boolean present;
    static final List<String> events = new ArrayList<>();

    public static class TestEvent {
        final String id;

        TestEvent(String id) {
            this.id = id;
        }
    }

    public static class Listener {
        @Order(0)
        @EventListener
        public void on(TestEvent e) {
            events.add(e.id);
        }
    }

    static class Consumer {
        final Optional<Listener> target;

        Consumer(Optional<Listener> target) {
            this.target = target;
        }
    }

    @Configuration
    public static class Config {
        @Bean
        public Listener listener() {
            return present ? new Listener() : null;
        }

        @Bean
        public Consumer consumer(Optional<Listener> value) {
            return new Consumer(value);
        }
    }

    public static class Observer {
        @Order(1)
        @EventListener
        public void on(TestEvent e) {
            events.add(e.id);
        }
    }

    public static String observe(String[] args) {
        present = args[0].equals("present");
        try (AnnotationConfigApplicationContext ctx = new AnnotationConfigApplicationContext()) {
            ctx.register(Config.class);
            if (args[0].equals("ordered")) ctx.register(Observer.class);
            ctx.refresh();
            String state = ctx.getBean(Consumer.class).target.isPresent() ? "present" : "empty";
            String status = "ok";
            try {
                ctx.publishEvent(new TestEvent("E1"));
                if (args[0].equals("ordered")) ctx.publishEvent(new TestEvent("E2"));
            } catch (RuntimeException e) {
                status = e.getClass().getSimpleName();
            }
            if (args[0].equals("ordered")) return status + ":" + events;
            if (present) return state + ":" + events;
            return state + ":" + status;
        }
    }
}
