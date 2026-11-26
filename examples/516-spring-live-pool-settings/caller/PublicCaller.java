import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.TimeUnit;

public class PublicCaller {
    static ThreadPoolTaskExecutor pool() {
        var pool = new ThreadPoolTaskExecutor();
        pool.setCorePoolSize(1);
        pool.setMaxPoolSize(1);
        pool.setKeepAliveSeconds(60);
        pool.afterPropertiesSet();
        return pool;
    }

    static String trySet(Runnable setter) {
        try {
            setter.run();
            return "ok";
        } catch (IllegalArgumentException e) {
            return e.getClass().getSimpleName();
        }
    }

    static String reject(int which) {
        var p = pool();
        var jdk = p.getThreadPoolExecutor();
        try {
            return switch (which) {
                case 0 ->
                        trySet(() -> p.setCorePoolSize(-1))
                                + ":"
                                + p.getCorePoolSize()
                                + "/"
                                + jdk.getCorePoolSize();
                case 1 ->
                        trySet(() -> p.setMaxPoolSize(0))
                                + ":"
                                + p.getMaxPoolSize()
                                + "/"
                                + jdk.getMaximumPoolSize();
                default ->
                        trySet(() -> p.setKeepAliveSeconds(-10))
                                + ":"
                                + p.getKeepAliveSeconds()
                                + "/"
                                + jdk.getKeepAliveTime(TimeUnit.SECONDS);
            };
        } finally {
            p.shutdown();
        }
    }

    public static String observe(String[] args) {
        if (args[0].equals("reject")) return reject(0) + " " + reject(1) + " " + reject(2);
        var p = pool();
        var jdk = p.getThreadPoolExecutor();
        try {
            if (args[0].equals("accept")) {
                p.setMaxPoolSize(3);
                p.setCorePoolSize(2);
                p.setKeepAliveSeconds(10);
                return p.getCorePoolSize()
                        + ","
                        + p.getMaxPoolSize()
                        + ","
                        + p.getKeepAliveSeconds()
                        + "/"
                        + jdk.getCorePoolSize()
                        + ","
                        + jdk.getMaximumPoolSize()
                        + ","
                        + jdk.getKeepAliveTime(TimeUnit.SECONDS);
            }
            String first = trySet(() -> p.setCorePoolSize(3));
            p.setMaxPoolSize(2);
            String second = trySet(() -> p.setCorePoolSize(p.getCorePoolSize() + 1));
            return first
                    + "/"
                    + second
                    + ":"
                    + p.getCorePoolSize()
                    + ","
                    + p.getMaxPoolSize()
                    + "/"
                    + jdk.getCorePoolSize()
                    + ","
                    + jdk.getMaximumPoolSize();
        } finally {
            p.shutdown();
        }
    }
}
