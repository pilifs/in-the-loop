import java.io.File;
import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/** Observe a supplied caller in its original namespace, with one ordered deployment per JVM. */
public final class LoaderObservations {
    static final class RecordingLoader extends URLClassLoader {
        final Set<String> events = new LinkedHashSet<>();
        final List<URL> providers;

        RecordingLoader(URL[] urls) {
            super(urls, ClassLoader.getPlatformClassLoader());
            providers = Arrays.asList(urls);
        }

        String origin(URL url) {
            if (url == null) return "absent";
            String address = url.toExternalForm();
            if (address.startsWith("jrt:/")) return address;
            for (int i = 0; i < providers.size(); i++) {
                String provider = providers.get(i).toExternalForm();
                if (address.equals(provider)) return Integer.toString(i);
                String prefix = "jar:" + provider + "!/";
                if (address.startsWith(prefix)) return i + "!/" + address.substring(prefix.length());
                if (provider.endsWith("/") && address.startsWith(provider))
                    return i + "!/" + address.substring(provider.length());
            }
            throw new IllegalStateException("origin outside the registered deployment: " + url);
        }

        @Override protected Class<?> findClass(String name) throws ClassNotFoundException {
            Class<?> result = super.findClass(name);
            events.add("class\t" + name + "\t" + origin(result.getProtectionDomain().getCodeSource().getLocation()));
            return result;
        }

        @Override public URL getResource(String name) {
            URL url = super.getResource(name);
            events.add("resource\t" + name + "\t" + origin(url));
            return url;
        }

        @Override public Enumeration<URL> getResources(String name) throws IOException {
            Enumeration<URL> urls = super.getResources(name);
            events.add("enumerate\t" + name);
            return new Enumeration<>() {
                int index;
                public boolean hasMoreElements() {
                    boolean next = urls.hasMoreElements();
                    if (!next) events.add("end\t" + name + "\t" + index);
                    return next;
                }
                public URL nextElement() {
                    URL item = urls.nextElement();
                    events.add("element\t" + name + "\t" + index++ + "\t" + origin(item));
                    return item;
                }
            };
        }
    }

    public static void main(String[] args) throws Throwable {
        List<String> rows = new ArrayList<>();
        String[] paths = args[2].split(Pattern.quote(File.pathSeparator));
        URL[] urls = new URL[paths.length];
        for (int i = 0; i < urls.length; i++) urls[i] = Path.of(paths[i]).toUri().toURL();
        boolean record = args[0].equals("record");
        try (RecordingLoader loader = new RecordingLoader(urls)) {
            ClassLoader active = record ? loader : ClassLoader.getSystemClassLoader();
            Thread thread = Thread.currentThread();
            ClassLoader prior = thread.getContextClassLoader();
            try {
                thread.setContextClassLoader(active);
                Class<?> api = Class.forName("ReferenceAPI", true, active);
                if (api.getClassLoader() != active || active.getParent() != ClassLoader.getPlatformClassLoader())
                    throw new IllegalStateException("unexpected defining loader");
                Method primary = api.getMethod("primary", int.class);
                Method control = api.getMethod("control", int.class);
                for (int i = 3; i < args.length; i++) {
                    int n = Integer.parseInt(args[i]);
                    rows.add("row\t" + n + "\t" + primary.invoke(null, n) + "\t" + control.invoke(null, n));
                }
            } catch (InvocationTargetException e) {
                throw e.getCause();
            } finally {
                thread.setContextClassLoader(prior);
                rows.addAll(loader.events);
                Files.write(Path.of(args[1]), rows);
            }
        }
    }
}
