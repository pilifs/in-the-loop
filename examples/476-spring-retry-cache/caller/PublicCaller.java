import java.io.IOException;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import reactor.core.Exceptions;
import reactor.core.publisher.Flux;
import org.springframework.cache.*;
import org.springframework.cache.annotation.*;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.cache.interceptor.SimpleKey;
import org.springframework.context.annotation.*;
import org.springframework.resilience.annotation.*;

public class PublicCaller {
    static final Duration LIMIT = Duration.ofSeconds(5);
    public static class Source {
        final AtomicInteger count = new AtomicInteger();
        boolean failFirst, prefix;
        Flux<String> stream() {
            return Flux.defer(() -> {
                if (count.incrementAndGet() == 1 && failFirst) {
                    Flux<String> error = Flux.error(new IOException("first subscription"));
                    return prefix ? Flux.just("partial").concatWith(error) : error;
                }
                return Flux.just("a","b");
            });
        }
    }
    public static class Service {
        final Source source;
        Service(Source source) { this.source = source; }
        @Cacheable("tests") @Retryable(maxRetries=2, delay=10) public Flux<String> cached() { return source.stream(); }
        @CacheEvict("tests") @Retryable(maxRetries=2, delay=10) public Flux<String> evict() { return source.stream(); }
    }
    @Configuration(proxyBeanMethods=false) @EnableCaching @EnableResilientMethods
    public static class Config {
        @Bean public CacheManager cacheManager() { return new ConcurrentMapCacheManager("tests"); }
        @Bean public Source source() { return new Source(); }
        @Bean public Service service(Source source) { return new Service(source); }
    }

    static Object stored(Cache cache) {
        var entry = cache.get(SimpleKey.EMPTY);
        return entry == null ? null : entry.get();
    }

    public static String observe(String[] args) {
        try (var context = new AnnotationConfigApplicationContext(Config.class)) {
            var service = context.getBean(Service.class);
            var source = context.getBean(Source.class);
            var cache = context.getBean(CacheManager.class).getCache("tests");
            if (args[0].equals("hit")) {
                var first = service.cached().collectList().block(LIMIT);
                var second = service.cached().collectList().block(LIMIT);
                return "first=" + first + " second=" + second + " subscriptions=" + source.count + " cache=" + stored(cache);
            }
            boolean eviction = args[0].equals("evict");
            if (eviction) cache.put(SimpleKey.EMPTY,List.of("old"));
            source.failFirst = true;
            source.prefix = args[0].equals("partial");
            var delivered = new ArrayList<String>();
            String terminal;
            try {
                (eviction ? service.evict() : service.cached()).doOnNext(delivered::add).timeout(LIMIT).blockLast();
                terminal = "complete";
            } catch (RuntimeException ex) {
                if (!(Exceptions.unwrap(ex) instanceof TimeoutException)) throw ex;
                terminal = "timeout";
            }
            String observed = "values=" + delivered + " terminal=" + terminal + " subscriptions=" + source.count + " cache=" + stored(cache);
            if (source.prefix && terminal.equals("complete")) {
                observed += " hit=" + service.cached().collectList().block(LIMIT) + " finalSubscriptions=" + source.count;
            }
            return observed;
        }
    }
}
