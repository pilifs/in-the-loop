import java.net.URI;
import org.wildfly.client.config.ClientConfiguration;

public final class ReferenceAPI {
    public static long primary(int n) {
        URI uri = n == 0 ? null : URI.create("file:/ordinary-config.xml");
        try {
            return ClientConfiguration.getInstance(uri).getConfigurationUri() == null ? 0 : 1;
        } catch (IllegalArgumentException ex) {
            return -1;
        }
    }
    public static long control(int n) {
        URI uri = URI.create("file:/ordinary-control.xml");
        return uri.equals(ClientConfiguration.getInstance(uri).getConfigurationUri()) ? 1 : 0;
    }
}
