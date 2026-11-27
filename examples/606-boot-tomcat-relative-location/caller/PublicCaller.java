import java.net.URI;
import java.net.http.*;
import jakarta.servlet.http.*;
import org.apache.catalina.core.StandardContext;
import org.springframework.boot.*;
import org.springframework.boot.tomcat.autoconfigure.servlet.TomcatServletWebServerAutoConfiguration;
import org.springframework.boot.web.servlet.ServletRegistrationBean;
import org.springframework.boot.web.server.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.annotation.*;

public class PublicCaller {
    @Configuration(proxyBeanMethods=false) @Import(TomcatServletWebServerAutoConfiguration.class)
    static class Config {
        @Bean ServletRegistrationBean<HttpServlet> redirect() {
            return new ServletRegistrationBean<>(new HttpServlet() {
                @Override protected void doGet(HttpServletRequest request, HttpServletResponse response) throws java.io.IOException {
                    response.sendRedirect("/login");
                }
            }, "/go");
        }
    }
    public static String observe(String[] args) throws Exception {
        boolean strict = args[0].equals("challenge");
        if (strict) System.setProperty("org.apache.catalina.STRICT_SERVLET_COMPLIANCE", "true");
        boolean bare = new StandardContext().getUseRelativeRedirects();
        var app = new SpringApplication(Config.class);
        app.setWebApplicationType(WebApplicationType.SERVLET);
        var settings = new java.util.ArrayList<>(java.util.List.of("--server.port=0", "--server.address=127.0.0.1"));
        if (args[0].equals("control")) settings.add("--server.tomcat.use-relative-redirects=false");
        try (var ctx = (ServletWebServerApplicationContext) app.run(settings.toArray(String[]::new))) {
            URI uri = URI.create("http://127.0.0.1:" + ctx.getWebServer().getPort() + "/go");
            var client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).followRedirects(HttpClient.Redirect.NEVER).build();
            var response = client.send(HttpRequest.newBuilder(uri).GET().build(), HttpResponse.BodyHandlers.discarding());
            URI location = URI.create(response.headers().firstValue("Location").orElseThrow());
            return (strict ? bare + "/" : "") + response.statusCode() + ":" + (location.isAbsolute() ? "absolute" : location)
                    + ":" + (uri.resolve("/login").equals(uri.resolve(location)) ? "same" : "different");
        }
    }
}
