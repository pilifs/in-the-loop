import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.springframework.boot.data.redis.autoconfigure.DataRedisConnectionDetails;

public class PublicCaller {
    static final String IMAGE = "redis:7.0.11@sha256:1008c73f08e9f913868e2fa2e843212b62ea5bf3c66435d87bc7a6207bc0f1b4";
    static String read(int tcp, int udp, boolean reverse) throws Exception {
        String tcpRow = "      - '127.0.0.1:" + tcp + ":6379/tcp'\n";
        String udpRow = udp > 0 ? "      - '127.0.0.1:" + udp + ":6379/udp'\n" : "";
        String service = "    image: " + IMAGE + "\n    ports:\n" + (reverse ? udpRow + tcpRow : tcpRow + udpRow)
                + "    healthcheck:\n      test: ['CMD','redis-cli','ping']\n      interval: 1s\n      timeout: 2s\n      retries: 15\n";
        try (var udpTcpGuard = new Socket()) {
            if (udp > 0) udpTcpGuard.bind(new InetSocketAddress(InetAddress.getLoopbackAddress(), udp));
            try (var project = new ComposeProject(service); var context = project.context()) {
            var details = context.getBean(DataRedisConnectionDetails.class).getStandalone();
            if (project.port(6379,"tcp") != tcp || (udp > 0 && project.port(6379,"udp") != udp)) throw new AssertionError("published ports differ");
            if (!InetAddress.getByName(details.getHost()).isLoopbackAddress()) throw new AssertionError("different host");
            if (details.getPort() != tcp && details.getPort() != udp) return "unexpected-port";
            try (var socket = new Socket()) {
                socket.connect(new InetSocketAddress(InetAddress.getLoopbackAddress(), details.getPort()), 1500);
                socket.setSoTimeout(1500);
                socket.getOutputStream().write("PING\r\n".getBytes(StandardCharsets.US_ASCII));
                String reply = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.US_ASCII)).readLine();
                return (details.getPort() == tcp ? "tcp:" : "udp:") + ("+PONG".equals(reply) ? "PONG" : "unexpected");
            } catch (ConnectException refused) {
                if (details.getPort() != udp) throw refused;
                return "udp:no-tcp-listener";
            }
            }
        }
    }
    static int freeUdp(int tcp, int excluded) throws IOException {
        try (var s = new DatagramSocket(0, InetAddress.getLoopbackAddress())) {
            return s.getLocalPort() == tcp || s.getLocalPort() == excluded ? freeUdp(tcp,excluded) : s.getLocalPort();
        }
    }
    public static String observe(String[] args) throws Exception {
        int tcp = ComposeProject.freeTcpPort();
        if (args[0].equals("control")) return read(tcp,0,false);
        int udp = freeUdp(tcp,0);
        String first = read(tcp,udp,false);
        return args[0].equals("challenge") ? first + "/" + read(tcp,freeUdp(tcp,udp),true) : first;
    }
}
