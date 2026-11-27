import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicReference;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.cache.autoconfigure.CacheAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.caffeine.CaffeineCache;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.context.annotation.Configuration;

public class PublicCaller {
    @Configuration(proxyBeanMethods = false) @EnableCaching static class Config {}
    public static String observe(String[] args) {
        var runner = new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(CacheAutoConfiguration.class))
                .withUserConfiguration(Config.class).withPropertyValues("spring.cache.type=caffeine");
        boolean control = args[0].equals("control"), dynamic = args[0].equals("challenge");
        if (!control) runner = runner.withPropertyValues("spring.cache.caffeine.cache-mode=async");
        if (!dynamic) runner = runner.withPropertyValues("spring.cache.cache-names=foo");
        var answer = new AtomicReference<String>();
        runner.run(ctx -> {
            var cache = (CaffeineCache) ctx.getBean(CaffeineCacheManager.class).getCache(dynamic ? "new-cache" : "foo");
            if (dynamic) {
                var loaded = cache.retrieve("k", () -> CompletableFuture.completedFuture("value"));
                answer.set(loaded.join() + "/" + cache.get("k", String.class));
            } else {
                cache.put("k", "value");
                boolean async;
                try { async = cache.getAsyncCache() != null; }
                catch (IllegalStateException noBacking) { async = false; }
                String result = cache.get("k", String.class) + ":" + async;
                if (!control) {
                    try {
                        Object returned = cache.retrieve("k").join();
                        if (returned instanceof org.springframework.cache.Cache.ValueWrapper wrapper)
                            result += ":wrapped:" + wrapper.get();
                        else result += ":direct:" + returned;
                    }
                    catch (IllegalStateException noBacking) { result += ":unavailable"; }
                }
                answer.set(result);
            }
        });
        return answer.get();
    }
}
