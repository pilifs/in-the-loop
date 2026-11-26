import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.*;
import org.springframework.mock.http.server.reactive.test.*;
import org.springframework.web.reactive.HandlerMapping;
import org.springframework.web.reactive.resource.ResourceWebHandler;
import org.springframework.web.server.adapter.DefaultServerWebExchange;
import org.springframework.web.server.session.DefaultWebSessionManager;

import reactor.core.publisher.Flux;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Pattern;

public class PublicCaller {
    static class Reply {
        int status;
        String body, range;
        long length;
        MediaType type;
    }

    static Reply get(String range) throws Exception {
        ResourceWebHandler handler = new ResourceWebHandler();
        handler.setLocations(
                Collections.singletonList(
                        new ClassPathResource("org/springframework/web/reactive/resource/test/")));
        handler.afterPropertiesSet();
        handler.afterSingletonsInstantiated();
        MockServerHttpRequest req = new MockServerHttpRequest(HttpMethod.GET, "/foo.txt");
        MockServerHttpResponse res = new MockServerHttpResponse();
        if (range != null) req.getHeaders().set("Range", "bytes=" + range);
        DefaultServerWebExchange ex =
                new DefaultServerWebExchange(req, res, new DefaultWebSessionManager());
        ex.getAttributes().put(HandlerMapping.PATH_WITHIN_HANDLER_MAPPING_ATTRIBUTE, "foo.txt");
        handler.handle(ex).blockMillis(5000);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        Flux.from(res.getBody())
                .doOnNext(
                        b -> {
                            byte[] part = new byte[b.readableByteCount()];
                            b.read(part);
                            bytes.write(part, 0, part.length);
                            DataBufferUtils.release(b);
                        })
                .then()
                .blockMillis(5000);
        Reply reply = new Reply();
        reply.status = res.getStatusCode() == null ? 200 : res.getStatusCode().value();
        reply.body = new String(bytes.toByteArray(), StandardCharsets.US_ASCII);
        reply.type = res.getHeaders().getContentType();
        reply.range = res.getHeaders().getFirst("Content-Range");
        reply.length = res.getHeaders().getContentLength();
        return reply;
    }

    public static String observe(String[] args) throws Exception {
        if (!args[0].equals("parts")) {
            Reply r = get(args[0].equals("full") ? null : "0-1");
            return r.status + ":" + r.range + ":" + r.length + ":" + r.body;
        }
        Reply multi = get("0-1,8-9");
        if (multi.type == null || multi.type.getParameter("boundary") == null)
            return "ordinary:" + multi.body;
        String boundary = multi.type.getParameter("boundary").replace("\"", "");
        List<String> regions = new ArrayList<>(), bodies = new ArrayList<>();
        for (String part : multi.body.split(Pattern.quote("--" + boundary), -1)) {
            if (!part.startsWith("\r\n") || !part.contains("\r\n\r\n")) continue;
            String[] pieces = part.substring(2).split("\r\n\r\n", 2);
            String body = pieces[1];
            if (!body.endsWith("\r\n")) throw new AssertionError("missing part terminator");
            body = body.substring(0, body.length() - 2);
            String range = null;
            for (String header : pieces[0].split("\r\n"))
                if (header.toLowerCase(Locale.ROOT).startsWith("content-range:"))
                    range = header.substring(header.indexOf(':') + 1).trim();
            regions.add(range + "=" + body);
            bodies.add(body);
        }
        return String.join(",", regions)
                + " singles="
                + bodies.equals(Arrays.asList(get("0-1").body, get("8-9").body));
    }
}
