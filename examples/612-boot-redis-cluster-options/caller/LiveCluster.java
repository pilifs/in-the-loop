import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.*;
import io.lettuce.core.cluster.ClusterClientOptions;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.ssl.SslAutoConfiguration;
import org.springframework.boot.data.redis.autoconfigure.*;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;

public class LiveCluster {
    static long topologyRequests(ComposeProject project, int port) throws Exception {
        String info = project.command("exec","-T","fixture","redis-cli","--no-auth-warning","-a","fixture-only",
                "-p",Integer.toString(port),"INFO","commandstats");
        var matches = Pattern.compile("(?m)^cmdstat_cluster\\|(nodes|slots|shards):calls=(\\d+)").matcher(info);
        long total = 0;
        while (matches.find()) total += Long.parseLong(matches.group(2));
        return total;
    }
    public static String observe() throws Exception {
        List<Integer> ports = new ArrayList<>();
        while (ports.size() < 3) {
            int p = ComposeProject.freeTcpPort();
            if (p < 54500 && !ports.contains(p) && !ports.contains(p-10000) && !ports.contains(p+10000)) ports.add(p);
        }
        StringBuilder service = new StringBuilder("    image: redis:8.6.2@sha256:832d7785830f3f4b559300e6191fc914b15642c1935252338825cf4332200148\n    ports:\n");
        for (int p : ports) service.append("      - '127.0.0.1:").append(p).append(":").append(p).append("/tcp'\n");
        service.append("    entrypoint: ['/bin/sh','-ec']\n    command:\n      - |\n");
        for (int p : ports) service.append("        mkdir -p /tmp/node-").append(p)
                .append("\n        redis-server --port ").append(p).append(" --dir /tmp/node-").append(p)
                .append(" --cluster-enabled yes --cluster-announce-ip 127.0.0.1 --cluster-config-file nodes.conf")
                .append(" --cluster-node-timeout 3000 --requirepass fixture-only --masterauth fixture-only --save '' --daemonize yes\n");
        String addresses = String.join(" ", ports.stream().map(p -> "127.0.0.1:" + p).toList());
        for (int port : ports) {
            service.append("        until redis-cli --no-auth-warning -a fixture-only -p ").append(port)
                    .append(" ping 2>/dev/null | grep -q PONG; do sleep 0.1; done\n");
        }
        service.append("        redis-cli --no-auth-warning -a fixture-only --cluster create ").append(addresses)
                .append(" --cluster-replicas 0 --cluster-yes\n        exec sleep infinity\n")
                .append("    healthcheck:\n      test: ['CMD-SHELL','redis-cli --no-auth-warning -a fixture-only -p ")
                .append(ports.getFirst()).append(" cluster info | grep -q cluster_state:ok']\n      interval: 1s\n      timeout: 2s\n      retries: 15\n");
        try (var project = new ComposeProject(service.toString())) {
            var result = new AtomicReference<String>();
            new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(DataRedisAutoConfiguration.class,SslAutoConfiguration.class))
                    .withPropertyValues("spring.data.redis.lettuce.cluster.refresh.period=1s","spring.data.redis.lettuce.cluster.refresh.adaptive=false")
                    .withBean(DataRedisConnectionDetails.class, () -> new DataRedisConnectionDetails() {
                        public String getPassword() { return "fixture-only"; }
                        public Cluster getCluster() { return () -> List.of(new Node("127.0.0.1",ports.get(0)), new Node("127.0.0.1",ports.get(1))); }
                    }).run(ctx -> {
                var factory = ctx.getBean(LettuceConnectionFactory.class);
                var options = factory.getClientConfiguration().getClientOptions().orElseThrow();
                boolean periodic = options instanceof ClusterClientOptions c && c.getTopologyRefreshOptions().isPeriodicRefreshEnabled();
                long period = options instanceof ClusterClientOptions c ? c.getTopologyRefreshOptions().getRefreshPeriod().toSeconds() : 0;
                try (var connection = factory.getClusterConnection()) {
                    connection.ping();
                    Thread.sleep(1600);
                    long before = topologyRequests(project, ports.get(2));
                    Thread.sleep(4500);
                    long after = topologyRequests(project, ports.get(2));
                    result.set(periodic + ":" + period + ":" + (after > before ? "increased" : "flat"));
                }
            });
            return result.get();
        }
    }
}
