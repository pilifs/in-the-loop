import java.net.InetAddress;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.stream.Address;
import com.rabbitmq.stream.Environment;
import org.springframework.boot.rabbitmq.autoconfigure.RabbitConnectionDetails;
import org.springframework.boot.rabbitmq.autoconfigure.RabbitStreamConnectionDetails;

public class PublicCaller {
    static final String IMAGE = "rabbitmq:4.2-management@sha256:a3afd4d8dcae7d2baccc92500da74516057ed3babb7d37cf405715bb7c798660";
    public static String observe(String[] args) throws Exception {
        boolean control = args[0].equals("control"), streams = args[0].equals("challenge");
        String service = "    image: " + IMAGE + "\n    environment:\n      RABBITMQ_DEFAULT_USER: fixture\n"
                + "      RABBITMQ_DEFAULT_PASS: fixture-only\n      RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS: '+S 2:2'\n"
                + (control ? "" : "      RABBITMQ_DEFAULT_VHOST: app\n")
                + "    ports:\n      - '127.0.0.1::5672/tcp'\n" + (streams ? "      - '127.0.0.1::5552/tcp'\n" : "")
                + "    healthcheck:\n      test: ['CMD','rabbitmq-diagnostics','-q','check_port_connectivity']\n      interval: 1s\n      timeout: 5s\n      retries: 30\n"
                + (streams ? "    configs:\n      - source: enabled\n        target: /etc/rabbitmq/enabled_plugins\nconfigs:\n  enabled:\n    content: '[rabbitmq_stream].'\n" : "");
        try (var project = new ComposeProject(service); var ctx = project.context()) {
            var classic = ctx.getBean(RabbitConnectionDetails.class);
            var endpoint = classic.getFirstAddress();
            if (!InetAddress.getByName(endpoint.host()).isLoopbackAddress() || endpoint.port() != project.port(5672,"tcp"))
                throw new AssertionError("unexpected broker");
            var factory = new ConnectionFactory();
            factory.setHost(endpoint.host());
            factory.setPort(endpoint.port());
            factory.setUsername(classic.getUsername());
            factory.setPassword(classic.getPassword());
            factory.setVirtualHost(classic.getVirtualHost());
            factory.setAutomaticRecoveryEnabled(false);
            factory.setConnectionTimeout(3000);
            String result = classic.getVirtualHost() + ":";
            try (var connection = factory.newConnection()) { result += connection.isOpen() ? "open" : "closed"; }
            catch (java.io.IOException rejected) { result += "refused"; }
            if (!streams) return result;
            var details = ctx.getBean(RabbitStreamConnectionDetails.class);
            var address = new Address(details.getHost(),details.getPort());
            if (!InetAddress.getByName(address.host()).isLoopbackAddress() || address.port() != project.port(5552,"tcp"))
                throw new AssertionError("unexpected stream broker");
            try (var environment = Environment.builder().host(address.host()).port(address.port()).addressResolver(a -> address)
                    .username(details.getUsername()).password(details.getPassword()).virtualHost(details.getVirtualHost()).build()) {
                return result + "/" + details.getVirtualHost() + ":" + environment.streamExists("absent-probe-stream");
            } catch (com.rabbitmq.stream.StreamException rejected) {
                return result + "/" + details.getVirtualHost() + ":refused";
            }
        }
    }
}
