import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import jakarta.servlet.http.Cookie;
import reactor.core.publisher.Mono;
import org.springframework.http.*;
import org.springframework.http.codec.HttpMessageWriter;
import org.springframework.web.reactive.result.view.*;
import org.springframework.web.servlet.function.RenderingResponse;
import org.springframework.web.testfixture.servlet.*;
import org.springframework.web.testfixture.server.MockServerWebExchange;
import org.springframework.web.testfixture.http.server.reactive.MockServerHttpRequest;

public class PublicCaller {
    static Cookie cookie(String name, String value, String path) {
        Cookie c = new Cookie(name, value);
        c.setPath(path);
        return c;
    }

    static ResponseCookie reactiveCookie(String name, String value, String path) {
        return ResponseCookie.from(name, value).path(path).build();
    }

    static String wire(Collection<String> lines) {
        var result = new ArrayList<String>();
        for (String line : lines) {
            String[] parts = line.split("; *");
            String path = Arrays.stream(parts).filter(s -> s.regionMatches(true, 0, "Path=", 0, 5))
                    .map(s -> s.substring(5)).findFirst().orElse("-");
            result.add(parts[0] + "@" + path);
        }
        Collections.sort(result);
        return result.toString();
    }

    static String mvc(String mode) throws Exception {
        var builder = RenderingResponse.create("checkout").status(HttpStatus.CREATED)
                .header("X-View","summary").modelAttribute("item","book");
        if (!mode.equals("plain")) builder.cookie(cookie("currency","EUR","/shop"));
        if (mode.equals("paths")) builder.cookie(cookie("currency","USD","/account"));
        var original = builder.build();
        var copyBuilder = RenderingResponse.from(original).modelAttribute("path","/cart");
        if (mode.equals("paths")) copyBuilder.cookie(cookie("visit","1","/"));
        var copy = copyBuilder.build();
        var response = new MockHttpServletResponse();
        var view = copy.writeTo(new MockHttpServletRequest("GET","/"), response, List::of);
        return view.getViewName() + "/" + response.getStatus() + "/" + response.getHeader("X-View") + "/"
                + view.getModel().get("item") + "/" + view.getModel().get("path") + " original=" + mvcCookies(original)
                + " copy=" + mvcCookies(copy) + " wire=" + wire(response.getHeaders("Set-Cookie"));
    }

    static List<String> mvcCookies(RenderingResponse r) {
        return r.cookies().values().stream().flatMap(Collection::stream)
                .map(c -> c.getName() + "=" + c.getValue() + "@" + c.getPath()).sorted().toList();
    }

    static List<String> fluxCookies(org.springframework.web.reactive.function.server.RenderingResponse r) {
        return r.cookies().values().stream().flatMap(Collection::stream)
                .map(c -> c.getName() + "=" + c.getValue() + "@" + c.getPath()).sorted().toList();
    }

    static String flux(String mode) {
        var builder = org.springframework.web.reactive.function.server.RenderingResponse.create("checkout")
                .status(HttpStatus.CREATED).header("X-View","summary").modelAttribute("item","book");
        if (!mode.equals("plain")) builder.cookie(reactiveCookie("currency","EUR","/shop"));
        if (mode.equals("paths")) builder.cookie(reactiveCookie("currency","USD","/account"));
        var original = builder.build().block();
        var copyBuilder = org.springframework.web.reactive.function.server.RenderingResponse.from(original).modelAttribute("path","/cart");
        if (mode.equals("paths")) copyBuilder.cookie(reactiveCookie("visit","1","/"));
        var copy = copyBuilder.build().block();
        var exchange = MockServerWebExchange.from(MockServerHttpRequest.get("/").build());
        var name = new AtomicReference<String>();
        var model = new AtomicReference<Map<String, ?>>();
        View view = (m, type, ex) -> { model.set(m); return ex.getResponse().setComplete(); };
        var context = new org.springframework.web.reactive.function.server.ServerResponse.Context() {
            public List<HttpMessageWriter<?>> messageWriters() { return List.of(); }
            public List<ViewResolver> viewResolvers() {
                return List.of((n, locale) -> { name.set(n); return Mono.just(view); });
            }
        };
        copy.writeTo(exchange, context).block();
        var res = exchange.getResponse();
        return name.get() + "/" + res.getStatusCode().value() + "/" + res.getHeaders().getFirst("X-View") + "/"
                + model.get().get("item") + "/" + model.get().get("path") + " original=" + fluxCookies(original)
                + " copy=" + fluxCookies(copy) + " wire=" + wire(res.getHeaders().getOrEmpty("Set-Cookie"));
    }

    public static String observe(String[] args) throws Exception {
        return "mvc=" + mvc(args[0]) + " flux=" + flux(args[0]);
    }
}
