import java.util.List;
import java.util.concurrent.atomic.AtomicReference;
import io.lettuce.core.cluster.ClusterClientOptions;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.ssl.SslAutoConfiguration;
import org.springframework.boot.data.redis.autoconfigure.*;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.data.redis.connection.RedisClusterConfiguration;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;

public class PublicCaller {
    static String query(String source) {
        var ctx = new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(DataRedisAutoConfiguration.class, SslAutoConfiguration.class))
                .withPropertyValues("spring.data.redis.lettuce.cluster.refresh.period=30s");
        if (source.equals("nodes")) ctx = ctx.withPropertyValues("spring.data.redis.cluster.nodes=127.0.0.1:27379,127.0.0.1:27380");
        else if (source.equals("bean")) ctx = ctx.withBean(RedisClusterConfiguration.class,
                () -> new RedisClusterConfiguration(List.of("127.0.0.1:27379", "127.0.0.1:27380")));
        else ctx = ctx.withBean(DataRedisConnectionDetails.class, () -> new DataRedisConnectionDetails() {
            @Override public Cluster getCluster() {
                return () -> List.of(new Node("127.0.0.1",27379), new Node("127.0.0.1",27380));
            }
        });
        var answer = new AtomicReference<String>();
        ctx.run(c -> {
            var factory = c.getBean(LettuceConnectionFactory.class);
            if (!factory.isClusterAware()) throw new AssertionError("factory is not clustered");
            var options = factory.getClientConfiguration().getClientOptions().orElseThrow();
            answer.set(options instanceof ClusterClientOptions cluster ? "cluster:" + cluster.getTopologyRefreshOptions()
                    .getRefreshPeriod().toSeconds() : "plain");
        });
        return answer.get();
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("challenge")) return LiveCluster.observe();
        return args[0].equals("control") ? query("nodes") : query("bean") + "/" + query("details");
    }
}
