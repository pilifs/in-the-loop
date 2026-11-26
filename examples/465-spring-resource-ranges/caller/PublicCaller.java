import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.file.attribute.FileTime;
import java.time.*;
import java.util.*;
import org.springframework.core.MethodParameter;
import org.springframework.core.io.*;
import org.springframework.http.*;
import org.springframework.http.converter.*;
import org.springframework.http.server.PathContainer;
import org.springframework.web.context.request.ServletWebRequest;
import org.springframework.web.context.support.StaticWebApplicationContext;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.function.*;
import org.springframework.web.servlet.mvc.method.annotation.HttpEntityMethodProcessor;
import org.springframework.web.servlet.resource.ResourceHttpRequestHandler;
import org.springframework.web.reactive.resource.ResourceWebHandler;
import org.springframework.web.testfixture.http.server.reactive.MockServerHttpRequest;
import org.springframework.web.testfixture.server.MockServerWebExchange;
import org.springframework.web.testfixture.servlet.*;
import org.springframework.web.util.ServletRequestPathUtils;
import org.springframework.web.util.pattern.PathPatternParser;

public class PublicCaller {
    static final long MODIFIED = Instant.parse("2021-02-25T12:00:00Z").toEpochMilli();
    static final String ETAG = "\"v2\"";
    final Resource location, file;
    final List<HttpMessageConverter<?>> converters = List.of(new ResourceHttpMessageConverter(), new ResourceRegionHttpMessageConverter());

    PublicCaller() throws Exception {
        Path dir = Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")), "asset");
        Path path = Files.writeString(dir.resolve("six.txt"), "abcdef", StandardCharsets.US_ASCII);
        Files.setLastModifiedTime(path, FileTime.fromMillis(MODIFIED));
        location = new UrlResource(dir.toUri());
        file = new FileSystemResource(path);
    }

    public ResponseEntity<Resource> controller() {
        return ResponseEntity.ok().lastModified(MODIFIED).eTag(ETAG).body(file);
    }

    record Reply(int status, String range, String body, String modified) {
        String result() { return status + "|" + Objects.toString(range, "-") + "|" + body; }
    }

    Reply receive(String route, String range, String validator) throws Exception {
        if (route.equals("webflux")) {
            var handler = new ResourceWebHandler();
            handler.setLocations(List.of(location));
            handler.setEtagGenerator(resource -> ETAG);
            handler.afterPropertiesSet();
            var request = MockServerHttpRequest.get("/six.txt");
            if (range != null) request.header(HttpHeaders.RANGE, range);
            if (validator != null) request.header(HttpHeaders.IF_RANGE, validator);
            var ex = MockServerWebExchange.from(request.build());
            ex.getAttributes().put(org.springframework.web.reactive.HandlerMapping.PATH_WITHIN_HANDLER_MAPPING_ATTRIBUTE,
                    PathContainer.parsePath("six.txt"));
            ex.getAttributes().put(org.springframework.web.reactive.HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE,
                    new PathPatternParser().parse("/**"));
            handler.handle(ex).block();
            var res = ex.getResponse();
            var h = res.getHeaders();
            res.setComplete().block();
            String body = res.getBodyAsString().block();
            return new Reply(res.getStatusCode() == null ? 200 : res.getStatusCode().value(), h.getFirst(HttpHeaders.CONTENT_RANGE),
                    Objects.toString(body, ""), h.getFirst(HttpHeaders.LAST_MODIFIED));
        }
        var req = new MockHttpServletRequest("GET","/six.txt");
        var res = new MockHttpServletResponse();
        if (range != null) req.addHeader(HttpHeaders.RANGE, range);
        if (validator != null) req.addHeader(HttpHeaders.IF_RANGE, validator);
        ServletRequestPathUtils.parseAndCache(req);
        switch (route) {
            case "static" -> {
                var handler = new ResourceHttpRequestHandler();
                handler.setApplicationContext(new StaticWebApplicationContext());
                handler.setServletContext(req.getServletContext());
                handler.setLocations(List.of(location));
                handler.setEtagGenerator(resource -> ETAG);
                handler.afterPropertiesSet();
                req.setAttribute(org.springframework.web.servlet.HandlerMapping.PATH_WITHIN_HANDLER_MAPPING_ATTRIBUTE, "six.txt");
                handler.handleRequest(req, res);
            }
            case "controller" -> new HttpEntityMethodProcessor(converters).handleReturnValue(controller(),
                    new MethodParameter(getClass().getMethod("controller"), -1), new ModelAndViewContainer(), new ServletWebRequest(req,res));
            case "functional" -> {
                var router = RouterFunctions.resource(RequestPredicates.GET("/six.txt"), file,
                        (r, h) -> { h.setETag(ETAG); h.setLastModified(MODIFIED); });
                var request = ServerRequest.create(req, converters);
                router.route(request).orElseThrow().handle(request).writeTo(req, res, () -> converters);
            }
            default -> throw new IllegalArgumentException(route);
        }
        return new Reply(res.getStatus(), res.getHeader(HttpHeaders.CONTENT_RANGE),
                new String(res.getContentAsByteArray(), StandardCharsets.US_ASCII), res.getHeader(HttpHeaders.LAST_MODIFIED));
    }

    String history(String route, String mode) throws Exception {
        String range = "bytes=1-3";
        return switch (mode) {
            case "stale" -> receive(route,range,"\"v1\"").result();
            case "matching" -> receive(route,range,null).result() + ";" + receive(route,range,ETAG).result();
            case "weak" -> receive(route,"bytes=broken","\"v1\"").result() + ";" + receive(route,range,"W/" + ETAG).result();
            case "date" -> {
                String emitted = Objects.requireNonNull(receive(route,null,null).modified());
                HttpHeaders dates = new HttpHeaders();
                dates.set(HttpHeaders.LAST_MODIFIED, emitted);
                dates.setLastModified(dates.getLastModified() + 1000);
                yield receive(route,range,emitted).result() + ";" + receive(route,range,dates.getFirst(HttpHeaders.LAST_MODIFIED)).result();
            }
            default -> throw new IllegalArgumentException(mode);
        };
    }

    public static String observe(String[] args) throws Exception {
        var caller = new PublicCaller();
        var result = new StringJoiner(" ");
        for (String route : List.of("static", "controller", "functional", "webflux")) {
            result.add(route + "=" + caller.history(route, args[0]));
        }
        return result.toString();
    }
}
