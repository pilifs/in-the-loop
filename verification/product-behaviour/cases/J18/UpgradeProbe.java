import java.util.*;
import java.util.concurrent.TimeUnit;
import javax.cache.Cache;
import javax.cache.CacheManager;
import javax.cache.Caching;
import com.github.benmanes.caffeine.cache.Expiry;
import com.github.benmanes.caffeine.jcache.configuration.CaffeineConfiguration;

public class UpgradeProbe {
    public static String observe(String[] args) {
        boolean size = !args[0].equals("expiry"), expiry = !args[0].equals("size");
        long life = args[1].equals("zero") ? 0 : TimeUnit.MINUTES.toNanos(1);
        StringBuilder calls = new StringBuilder();
        CaffeineConfiguration<Integer,Integer> config = new CaffeineConfiguration<>();
        config.setTypes(Integer.class, Integer.class);
        config.setStoreByValue(false);
        config.setExecutorFactory(() -> Runnable::run);
        config.setTickerFactory(() -> () -> 1000000000L);
        if (size) config.setMaximumSize(OptionalLong.of(2));
        if (expiry) config.setExpiryFactory(Optional.of(() -> new Expiry<Integer,Integer>() {
            public long expireAfterCreate(Integer k, Integer v, long now) { calls.append('C'); return life; }
            public long expireAfterUpdate(Integer k, Integer v, long now, long previous) { calls.append('U'); return life; }
            public long expireAfterRead(Integer k, Integer v, long now, long previous) { calls.append('R'); return life; }
        }));
        try (CacheManager manager = Caching.getCachingProvider().getCacheManager()) {
            Cache<Integer,Integer> cache = manager.createCache("items", config);
            cache.put(1,10); cache.put(1,20);
            Integer first = cache.get(1), second = cache.get(1);
            String result = first + "/" + second + "/" + calls;
            if (args[1].equals("maintenance")) {
                for (int i=2; i<=9; i++) cache.put(i,i*10);
                com.github.benmanes.caffeine.cache.Cache<?,?> nativeCache = cache.unwrap(com.github.benmanes.caffeine.cache.Cache.class);
                nativeCache.cleanUp();
                long count = nativeCache.estimatedSize();
                int entries=0;
                for (Cache.Entry<Integer,Integer> row : cache) {
                    if (row.getValue() != row.getKey() * 10 && !(row.getKey() == 1 && row.getValue() == 20))
                        throw new AssertionError("entry's value changed");
                    entries++;
                }
                result += "/size=" + count + "/visible=" + entries;
            }
            return result;
        }
    }
}
