import java.util.*;
import org.springframework.boot.health.contributor.*;
import org.springframework.context.annotation.*;

public class PublicCaller {
    @Configuration(proxyBeanMethods=false) static class Markers {
        @Bean HealthIndicator near() { return () -> Health.up().build(); }
        @Bean HealthIndicator far() { return () -> Health.up().build(); }
    }
    static void group(List<String> out,String name,String indicator,String path) {
        String key = "management.endpoint.health.group." + name + ".";
        out.add(key + "include=" + indicator);
        out.add(key + "additional-path=server:" + path);
        out.add(key + "show-components=always");
    }
    static String two(boolean reverse) throws Exception {
        List<String> props = new ArrayList<>();
        if (!reverse) group(props,"nearby","near","/probe");
        group(props,"distant","far","/probe/deep");
        if (reverse) group(props,"nearby","near","/probe");
        try (var app = new HealthHttp(Markers.class,props.toArray(String[]::new))) {
            return app.get("/probe",true) + "/" + app.get("/probe/deep",true) + "/" + app.get("/probe/deep/far",false);
        }
    }
    public static String observe(String[] args) throws Exception {
        if (args[0].equals("challenge")) return two(false) + ";" + two(true);
        String path = args[0].equals("control") ? "/healthz" : "/myBasePath/health";
        List<String> props = new ArrayList<>();
        group(props,"live","diskSpace",path);
        try (var app = new HealthHttp(Markers.class,props.toArray(String[]::new))) { return app.get(path,true); }
    }
}
