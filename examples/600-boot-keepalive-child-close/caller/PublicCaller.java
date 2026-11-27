import java.io.*;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;
import org.springframework.boot.Banner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Configuration;

public class PublicCaller {
    @Configuration(proxyBeanMethods = false) static class Config {}

    public static void main(String[] args) throws Exception {
        if (!SpringApplication.class.getProtectionDomain().getCodeSource().getLocation().toString().equals(args[1]))
            throw new AssertionError("child loaded different Spring Boot bytes");
        var app = new SpringApplication(Config.class);
        app.setWebApplicationType(WebApplicationType.NONE);
        app.setBannerMode(Banner.Mode.OFF);
        app.setKeepAlive(true);
        var parent = app.run();
        var sibling = new AnnotationConfigApplicationContext();
        if (args[0].equals("control")) parent.close();
        else {
            if (args[0].equals("challenge")) {
                sibling.setParent(parent);
                sibling.registerBean("marker", String.class, () -> "sibling");
                sibling.refresh();
            }
            try (var first = new AnnotationConfigApplicationContext()) {
                first.setParent(parent);
                first.refresh();
            }
        }
        System.out.println("FIXTURE " + (parent.isActive() ? "active" : "inactive"));
        System.out.flush();
        if (args[0].equals("control")) return;
        Thread main = Thread.currentThread();
        Thread thread = new Thread(() -> {
            try {
                main.join();
                if (new BufferedReader(new InputStreamReader(System.in)).readLine() != null) {
                    String marker = sibling.isActive() ? sibling.getBean("marker", String.class) : "parent";
                    System.out.println("FIXTURE reply:" + marker);
                    System.out.flush();
                }
            } catch (Exception ex) { throw new IllegalStateException(ex); }
            finally {
                if (sibling.isActive()) sibling.close();
                parent.close();
            }
        });
        thread.setDaemon(true);
        thread.start();
    }
    static String marker(BufferedReader lines) throws IOException {
        String line;
        while ((line = lines.readLine()) != null) if (line.startsWith("FIXTURE ")) return line.substring(8);
        return "no-reply";
    }
    public static String observe(String[] args) throws Exception {
        Path java = Path.of(System.getProperty("java.home"), "bin", "java");
        Process child = new ProcessBuilder(java.toString(), "-Xmx128m", "-cp", System.getProperty("java.class.path"),
                PublicCaller.class.getName(), args[0], SpringApplication.class.getProtectionDomain().getCodeSource()
                .getLocation().toString()).redirectErrorStream(true).start();
        try (var lines = child.inputReader()) {
            String state = marker(lines);
            if (child.waitFor(1, TimeUnit.SECONDS)) return state + ":exited:" + child.exitValue();
            child.getOutputStream().write(10);
            child.getOutputStream().flush();
            String response = marker(lines);
            if (!child.waitFor(8, TimeUnit.SECONDS)) throw new AssertionError("owner close did not terminate JVM");
            return state + ":" + response + ":" + child.exitValue();
        } finally { if (child.isAlive()) child.destroyForcibly(); }
    }
}
