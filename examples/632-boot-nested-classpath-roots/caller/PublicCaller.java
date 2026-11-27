import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.apache.commons.logging.LogFactory;

public class PublicCaller {
    static byte[] bytes(String s) { return s.getBytes(StandardCharsets.US_ASCII); }
    public static String observe(String[] args) throws Exception {
        var resources = new LinkedHashMap<String,byte[]>();
        resources.put("root-marker.properties",bytes("app"));
        resources.put("mapper/",new byte[0]);
        resources.put("mapper/fixed.xml",bytes("xml"));
        var libs = new LinkedHashMap<String,byte[]>();
        libs.put("first.jar", BootArchive.library(BootArchive.manifest(), Map.of("library-marker.properties", bytes("A"))));
        libs.put("second.jar", BootArchive.library(BootArchive.manifest(), Map.of("library-marker.properties", bytes("B"))));
        libs.put("spring-core.jar", BootArchive.codeSource(PathMatchingResourcePatternResolver.class));
        libs.put("commons-logging.jar", BootArchive.codeSource(LogFactory.class));
        return BootArchive.launch(NestedApp.class,resources,libs,args[0]);
    }
}
