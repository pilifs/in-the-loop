import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import org.springframework.context.annotation.*;
import org.springframework.mock.web.MockServletContext;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.reactive.config.EnableWebFlux;
import org.springframework.web.reactive.config.WebFluxConfigurer;
import org.springframework.web.service.annotation.*;
import org.springframework.web.servlet.config.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

public class PublicCaller {
    static final AtomicInteger calls = new AtomicInteger();

    @RestController
    @HttpExchange("/foo")
    public static class ExchangeRoutes {
        @GetExchange
        public String base() {
            calls.incrementAndGet();
            return "base";
        }

        @GetExchange(version = "1.1")
        public String version() {
            calls.incrementAndGet();
            return "v1.1";
        }
    }

    @RestController
    @RequestMapping("/foo")
    public static class OrdinaryRoutes {
        @GetMapping
        public String base() {
            calls.incrementAndGet();
            return "base";
        }

        @GetMapping(version = "1.1")
        public String version() {
            calls.incrementAndGet();
            return "v1.1";
        }
    }

    @Configuration(proxyBeanMethods = false)
    @EnableWebMvc
    public static class Mvc implements WebMvcConfigurer {
        public void configureApiVersioning(ApiVersionConfigurer versions) {
            versions.useRequestHeader("API-Version").detectSupportedVersions(true);
        }
    }

    @Configuration(proxyBeanMethods = false)
    @EnableWebFlux
    public static class Reactive implements WebFluxConfigurer {
        public void configureApiVersioning(
                org.springframework.web.reactive.config.ApiVersionConfigurer versions) {
            versions.useRequestHeader("API-Version").detectSupportedVersions(true);
        }
    }

    static String describe(int status, String body) {
        return status + ":" + (status == 200 ? body + ":" : "") + calls.get();
    }

    static String mvc(Class<?> routes, String version) throws Exception {
        calls.set(0);
        try (var context = new AnnotationConfigWebApplicationContext()) {
            var servletContext = new MockServletContext();
            context.setServletContext(servletContext);
            context.register(Mvc.class, routes);
            context.refresh();
            var mvc = MockMvcBuilders.webAppContextSetup(context).build();
            var res =
                    mvc.perform(get("/foo").header("API-Version", version))
                            .andReturn()
                            .getResponse();
            return describe(res.getStatus(), res.getContentAsString());
        }
    }

    static String flux(Class<?> routes, String version) {
        calls.set(0);
        try (var context = new AnnotationConfigApplicationContext(Reactive.class, routes)) {
            var client = WebTestClient.bindToApplicationContext(context).build();
            var res =
                    client.get()
                            .uri("/foo")
                            .header("API-Version", version)
                            .exchange()
                            .expectBody()
                            .returnResult();
            int status = res.getStatus().value();
            return describe(
                    status,
                    status == 200 ? new String(res.getResponseBody(), StandardCharsets.UTF_8) : "");
        }
    }

    static String dispatch(boolean reactive, Class<?> routes, String version) throws Exception {
        try {
            return reactive ? flux(routes, version) : mvc(routes, version);
        } catch (RuntimeException failure) {
            for (Throwable e = failure; e != null; e = e.getCause())
                if (e.getMessage() != null && e.getMessage().contains("Ambiguous mapping"))
                    return "ambiguous";
            throw failure;
        }
    }

    public static String observe(String[] args) throws Exception {
        if (args[0].equals("request"))
            return dispatch(false, OrdinaryRoutes.class, "1.1")
                    + " / "
                    + dispatch(false, OrdinaryRoutes.class, "99");
        String first = dispatch(false, ExchangeRoutes.class, "1.1");
        if (args[0].equals("exchange")) return first;
        return first
                + " / "
                + dispatch(false, ExchangeRoutes.class, "99")
                + " | "
                + dispatch(true, ExchangeRoutes.class, "1.1")
                + " / "
                + dispatch(true, ExchangeRoutes.class, "99");
    }
}
