import org.aopalliance.intercept.MethodInterceptor;
import org.springframework.web.service.annotation.GetExchange;
import org.springframework.web.service.invoker.*;

import java.lang.reflect.Proxy;
import java.util.*;

public class PublicCaller {
    public interface Service {
        @GetExchange("/probe")
        String read();
    }

    public static String observe(String[] args) {
        List<List<String>> headers = new ArrayList<>();
        var adapter =
                (HttpExchangeAdapter)
                        Proxy.newProxyInstance(
                                PublicCaller.class.getClassLoader(),
                                new Class[] {HttpExchangeAdapter.class},
                                (p, m, a) -> {
                                    if (m.getName().equals("supportsRequestAttributes"))
                                        return false;
                                    if (m.getName().equals("exchangeForBody")) {
                                        var request = (HttpRequestValues) a[0];
                                        headers.add(
                                                List.copyOf(
                                                        request.getHeaders()
                                                                .getOrDefault(
                                                                        "X-Stage", List.of())));
                                        return "base";
                                    }
                                    throw new UnsupportedOperationException(m.getName());
                                });
        var builder = HttpServiceProxyFactory.builderFor(adapter);
        var first = builder.build();
        if (args[0].equals("advice"))
            builder.proxyFactoryCustomizer(
                    (pf, type) -> pf.addAdvice(0, (MethodInterceptor) invocation -> "late"));
        if (args[0].equals("header"))
            builder.httpRequestValuesProcessor(
                    (m, params, arguments, values) -> values.addHeader("X-Stage", "late"));
        var second = builder.build();
        List<String> result = new ArrayList<>();
        result.add(first.createClient(Service.class).read());
        result.add(second.createClient(Service.class).read());
        if (args[0].equals("header")) result.add(first.createClient(Service.class).read());
        return result + ":" + headers;
    }
}
