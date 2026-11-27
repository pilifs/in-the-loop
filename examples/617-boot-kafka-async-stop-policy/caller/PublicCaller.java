import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.ssl.SslAutoConfiguration;
import org.springframework.boot.kafka.autoconfigure.KafkaAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;

public class PublicCaller {
    static String read(String setting) {
        var runner = new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(KafkaAutoConfiguration.class, SslAutoConfiguration.class))
                .withPropertyValues("spring.kafka.admin.auto-create=false");
        if (setting != null) runner = runner.withPropertyValues("spring.kafka.listener.await-async-results-on-stop=" + setting);
        var value = new AtomicReference<String>();
        runner.run(ctx -> {
            var factory = ctx.getBean(ConcurrentKafkaListenerContainerFactory.class);
            var actual = factory.createContainer("fixture");
            value.set(factory.getContainerProperties().isAwaitAsyncResultsOnStop() + ":" + actual.getContainerProperties().isAwaitAsyncResultsOnStop());
        });
        return value.get();
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("challenge")) return PendingListener.observe();
        return args[0].equals("control") ? read(null) + "/" + read("false") : read("true");
    }
}
