import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;
import java.util.Collections;
import java.util.ServiceConfigurationError;
import civil.Hours;

public final class ChronologyContext {
    public static void main(String[] args) throws Exception {
        String resource = "META-INF/services/org.threeten.bp.chrono.Chronology";
        Thread thread = Thread.currentThread();
        ClassLoader application = thread.getContextClassLoader();
        URL providerRoot = Path.of(args[0]).toUri().toURL();
        try (URLClassLoader context = new URLClassLoader(new URL[] {providerRoot}, application)) {
            thread.setContextClassLoader(context);
            System.out.println("application=" + Collections.list(application.getResources(resource)).size());
            System.out.println("context=" + Collections.list(context.getResources(resource)).size());
            try {
                System.out.println("hours=" + Hours.completeHours(94, 97));
            } catch (ServiceConfigurationError failure) {
                System.out.println("error=" + failure.getClass().getName());
                System.out.println("message=" + failure.getMessage());
            } finally {
                thread.setContextClassLoader(application);
            }
        }
    }
}
