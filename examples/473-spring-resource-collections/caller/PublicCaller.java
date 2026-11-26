import java.net.URLClassLoader;
import java.nio.file.*;
import java.util.*;
import org.springframework.beans.BeansException;
import org.springframework.context.support.ClassPathXmlApplicationContext;
import org.springframework.core.io.Resource;

public class PublicCaller {
    public static class Holder {
        private List<Resource> list;
        private Set<Resource> set;
        public void setList(List<Resource> v) { list = v; }
        public void setSet(Set<Resource> v) { set = v; }
        public List<Resource> getList() { return list; }
        public Set<Resource> getSet() { return set; }
    }

    static List<String> bytes(Collection<Resource> resources) throws Exception {
        var values = new ArrayList<String>();
        for (Resource r : resources) {
            try (var in = r.getInputStream()) { values.add(HexFormat.of().formatHex(in.readAllBytes())); }
        }
        Collections.sort(values);
        return values;
    }

    static String refresh(boolean wildcard, boolean two) throws Exception {
        var root = Files.createTempDirectory(Path.of(System.getProperty("java.io.tmpdir")), "classpath");
        var dir = Files.createDirectory(root.resolve("fixtures"));
        Files.copy(Path.of("fixtures/one.txt"), dir.resolve("one.txt"));
        if (two) Files.copy(Path.of("fixtures/two.txt"), dir.resolve("two.txt"));
        String location = wildcard ? "classpath*:fixtures/*.txt" : "classpath:fixtures/one.txt";
        Files.writeString(root.resolve("context.xml"), Files.readString(Path.of("fixtures/context.xml")).replace("@LOCATION@",location));
        try (var loader = new URLClassLoader(new java.net.URL[]{root.toUri().toURL()}, PublicCaller.class.getClassLoader());
             var context = new ClassPathXmlApplicationContext()) {
            context.setClassLoader(loader);
            context.setConfigLocation("classpath:context.xml");
            try { context.refresh(); }
            catch (BeansException e) { return "refresh=" + e.getClass().getSimpleName() + " cause=" + e.getMostSpecificCause().getClass().getSimpleName(); }
            var b = context.getBean(Holder.class);
            return "list=" + bytes(b.getList()) + " set=" + bytes(b.getSet());
        }
    }

    public static String observe(String[] args) throws Exception {
        return switch (args[0]) {
            case "literal" -> refresh(false,false);
            case "two" -> refresh(true,true);
            case "singletons" -> "literal=" + refresh(false,false) + " wildcard=" + refresh(true,false);
            default -> throw new IllegalArgumentException(args[0]);
        };
    }
}
