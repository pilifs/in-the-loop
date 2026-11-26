import java.time.Duration;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import reactor.core.publisher.*;
import reactor.util.context.Context;
import org.springframework.cache.*;
import org.springframework.cache.annotation.*;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.*;

public class PublicCaller {
    static final Duration LIMIT = Duration.ofSeconds(5);
    public static class Service {
        private final AtomicInteger subscriptions;
        Service(AtomicInteger count) { subscriptions = count; }
        Flux<String> source() {
            return Flux.deferContextual(c -> {
                subscriptions.incrementAndGet();
                return Flux.just(c.<String>getOrDefault("tenant","none"));
            });
        }
        @Cacheable("first") public Flux<String> lookup(String key) { return source(); }
        @Cacheable("first") public Mono<String> mono(String key) {
            return Mono.deferContextual(c -> {
                subscriptions.incrementAndGet();
                return Mono.just(c.<String>getOrDefault("tenant","none"));
            });
        }
        @CachePut("first") public Flux<String> put(String key) { return source(); }
        @CacheEvict("first") public Flux<String> evict(String key) { return source(); }
    }
    @Configuration(proxyBeanMethods=false) @EnableCaching
    public static class Config {
        @Bean public CacheManager cacheManager() { return new ConcurrentMapCacheManager("first"); }
        @Bean public AtomicInteger subscriptions() { return new AtomicInteger(); }
        @Bean public Service service(AtomicInteger count) { return new Service(count); }
    }

    static List<String> collect(Flux<String> stream, String value) {
        return stream.contextWrite(Context.of("tenant",value)).collectList().block(LIMIT);
    }
    static Object stored(Cache cache) {
        var entry = cache.get("k");
        return entry == null ? null : entry.get();
    }

    public static String observe(String[] args) {
        try (var context = new AnnotationConfigApplicationContext(Config.class)) {
            var service = context.getBean(Service.class);
            var count = context.getBean(AtomicInteger.class);
            var cache = context.getBean(CacheManager.class).getCache("first");
            return switch (args[0]) {
                case "flux" -> "first=" + collect(service.lookup("k"),"t1") + " second=" + collect(service.lookup("k"),"t2")
                        + " subscriptions=" + count + " cache=" + stored(cache);
                case "mono" -> "first=" + service.mono("k").contextWrite(Context.of("tenant","t1")).block(LIMIT)
                        + " second=" + service.mono("k").contextWrite(Context.of("tenant","t2")).block(LIMIT)
                        + " subscriptions=" + count + " cache=" + stored(cache);
                case "write" -> "put=" + collect(service.put("k"),"t1") + " stored=" + stored(cache)
                        + " evict=" + collect(service.evict("k"),"t2") + " final=" + stored(cache) + " subscriptions=" + count;
                case "defer" -> {
                    var saved = service.lookup("k");
                    var first = collect(saved,"t1");
                    cache.evict("k");
                    boolean empty = cache.get("k") == null;
                    yield "first=" + first + " empty=" + empty + " second=" + collect(service.lookup("k"),"t2")
                            + " subscriptions=" + count + " cache=" + stored(cache);
                }
                default -> throw new IllegalArgumentException(args[0]);
            };
        }
    }
}
