import java.net.*;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import jakarta.servlet.http.*;
import org.springframework.boot.jetty.servlet.JettyServletWebServerFactory;
import org.springframework.boot.tomcat.servlet.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.Shutdown;
import org.springframework.boot.web.server.servlet.ConfigurableServletWebServerFactory;

public class PublicCaller {
    static String run(ConfigurableServletWebServerFactory factory, String mode) throws Exception {
        int n = mode.equals("challenge") ? 2 : 1;
        var admitted = new CountDownLatch(n);
        var gates = new CountDownLatch[n];
        Arrays.setAll(gates, i -> new CountDownLatch(1));
        var finished = new AtomicInteger();
        factory.setPort(0);
        factory.setAddress(InetAddress.getByName("127.0.0.1"));
        factory.setShutdown(Shutdown.GRACEFUL);
        var server = factory.getWebServer(context -> context.addServlet("blocking", new HttpServlet() {
            @Override protected void doGet(HttpServletRequest request, HttpServletResponse response) throws java.io.IOException {
                int index = Integer.parseInt(request.getParameter("id"));
                admitted.countDown();
                try {
                    if (!gates[index].await(10,TimeUnit.SECONDS)) throw new java.io.IOException("fixture release timed out");
                } catch (InterruptedException interrupted) { Thread.currentThread().interrupt(); throw new java.io.IOException(interrupted); }
                response.setStatus(200);
                response.getWriter().write("finished");
                finished.incrementAndGet();
            }
        }).addMapping("/blocking"));
        try {
            server.start();
            if (!mode.equals("control")) { server.stop(); server.start(); }
            var requests = new ArrayList<CompletableFuture<HttpResponse<String>>>();
            try (var client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).build()) {
                for (int i=0; i<n; i++) requests.add(client.sendAsync(HttpRequest.newBuilder(
                        URI.create("http://127.0.0.1:" + server.getPort() + "/blocking?id=" + i))
                        .timeout(Duration.ofSeconds(12)).GET().build(), HttpResponse.BodyHandlers.ofString()));
                if (!admitted.await(8,TimeUnit.SECONDS)) throw new AssertionError("request did not enter servlet");
                var callback = new CompletableFuture<String>();
                server.shutDownGracefully(status -> callback.complete(status + "@" + finished.get()));
                var replies = new ArrayList<String>();
                for (int i=0; i<n; i++) {
                    gates[i].countDown();
                    try {
                        var response = requests.get(i).get(8, TimeUnit.SECONDS);
                        replies.add(response.statusCode() + ":" + response.body());
                    } catch (ExecutionException lost) { replies.add("lost"); }
                }
                return callback.get(8,TimeUnit.SECONDS) + ":" + replies;
            }
        } finally {
            for (var gate : gates) gate.countDown();
            server.stop();
            server.destroy();
        }
    }
    public static String observe(String[] args) throws Exception {
        return run(new TomcatServletWebServerFactory(), args[0]) + "/" + run(new JettyServletWebServerFactory(), args[0]);
    }
}
