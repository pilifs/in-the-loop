import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.ssl.SslAutoConfiguration;
import org.springframework.boot.kafka.autoconfigure.KafkaAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.*;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.config.KafkaListenerEndpointRegistry;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.test.EmbeddedKafkaKraftBroker;

public class PendingListener {
    static final CountDownLatch entered = new CountDownLatch(1);
    static final CompletableFuture<Void> future = new CompletableFuture<>();
    public static class Handler {
        @KafkaListener(id="probe-listener",topics="fixture-topic")
        public CompletableFuture<Void> receive(String message) {
            if (!"owned-record".equals(message)) throw new AssertionError("wrong record");
            entered.countDown();
            return future;
        }
    }
    @Configuration(proxyBeanMethods=false) static class Config {
        @Bean Handler handler() { return new Handler(); }
    }
    @SuppressWarnings("unchecked")
    public static String observe() throws Exception {
        var broker = new EmbeddedKafkaKraftBroker(1,1,"fixture-topic");
        try {
            broker.afterPropertiesSet();
            var result = new AtomicReference<String>();
            new ApplicationContextRunner().withUserConfiguration(Config.class)
                    .withConfiguration(AutoConfigurations.of(KafkaAutoConfiguration.class,SslAutoConfiguration.class))
                    .withPropertyValues("spring.kafka.bootstrap-servers=" + broker.getBrokersAsString(),
                            "spring.kafka.consumer.auto-offset-reset=earliest", "spring.kafka.listener.await-async-results-on-stop=true")
                    .run(ctx -> {
                var container = ctx.getBean(KafkaListenerEndpointRegistry.class).getListenerContainer("probe-listener");
                container.getContainerProperties().setShutdownTimeout(6000);
                KafkaTemplate<Object,Object> producer = ctx.getBean(KafkaTemplate.class);
                producer.send("fixture-topic","owned-record").get(8,TimeUnit.SECONDS);
                if (!entered.await(10,TimeUnit.SECONDS)) throw new AssertionError("message never entered listener");
                var stopped = new CompletableFuture<Boolean>();
                container.stop(() -> stopped.complete(future.isDone() && !future.isCancelled()));
                long limit = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
                while (container.isRunning() && System.nanoTime() < limit) Thread.sleep(10);
                boolean stopping = !container.isRunning();
                boolean early;
                try { stopped.get(250,TimeUnit.MILLISECONDS); early = true; }
                catch (TimeoutException pending) { early = false; }
                boolean released = future.complete(null);
                boolean after = stopped.get(8,TimeUnit.SECONDS);
                result.set("stopping:" + stopping + "/future:" + (released && !future.isCompletedExceptionally() ? "normal" : "cancelled")
                        + "/callback:" + (!early && after ? "after" : "before"));
            });
            return result.get();
        } finally { future.complete(null); broker.destroy(); }
    }
}
