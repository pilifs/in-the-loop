package styles;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLStreamHandler;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Enumeration;
import java.util.Set;

public final class World {
    static final String SERVICE = "META-INF/services/styleapi.PageStyle";
    static final String[] TEXT = {"", "providers.Compact\n", "providers.Compact\nproviders.Wide\n",
                                 "providers.Wide\nproviders.Compact\n"};

    static final class Layer extends ClassLoader {
        private final Set<String> classes;
        private final URL resource;

        Layer(String name, ClassLoader parent, Set<String> classes, String descriptor) throws Exception {
            super(name, parent);
            this.classes = classes;
            if (descriptor == null) {
                resource = null;
            } else {
                byte[] bytes = descriptor.getBytes(StandardCharsets.UTF_8);
                resource = new URL(null, "memory:/" + name + "/" + SERVICE, new URLStreamHandler() {
                    protected URLConnection openConnection(URL url) {
                        return new URLConnection(url) {
                            public void connect() {}
                            public InputStream getInputStream() { return new ByteArrayInputStream(bytes); }
                        };
                    }
                });
            }
        }

        protected Class<?> findClass(String name) throws ClassNotFoundException {
            if (!classes.contains(name)) throw new ClassNotFoundException(name);
            String path = "/" + name.replace('.', '/') + ".class";
            try (InputStream in = World.class.getResourceAsStream(path)) {
                if (in == null) throw new ClassNotFoundException(name);
                byte[] bytes = in.readAllBytes();
                return defineClass(name, bytes, 0, bytes.length);
            } catch (IOException e) {
                throw new ClassNotFoundException(name, e);
            }
        }

        protected Enumeration<URL> findResources(String name) {
            return resource != null && name.equals(SERVICE) ? Collections.enumeration(Collections.singleton(resource))
                                                           : Collections.emptyEnumeration();
        }
    }

    private static Set<String> visible(int profile) {
        return profile == 0 ? Set.of() : profile == 1 ? Set.of("providers.Compact") : Set.of("providers.Compact","providers.Wide");
    }

    public static String[][] sequence(int code) throws Exception {
        ClassLoader original = Thread.currentThread().getContextClassLoader();
        Layer common = new Layer("api", ClassLoader.getPlatformClassLoader(),
                                 Set.of("styleapi.PageStyle", "styleapi.Construction"), null);
        Layer application = new Layer("application", common, Set.of("styles.Lookup","providers.Compact"), TEXT[1]);
        Class<?> lookup = application.loadClass("styles.Lookup");
        String[][] result = new String[2][];
        try {
            for (int i = 0; i < 2; i++) {
                int profile = i == 0 ? code / 4 : code % 4;
                Layer context = new Layer("context" + i, common, visible(profile), TEXT[profile]);
                Thread.currentThread().setContextClassLoader(context);
                result[i] = (String[]) lookup.getMethod("inspect").invoke(null);
            }
        } finally {
            Thread.currentThread().setContextClassLoader(original);
        }
        return result;
    }

    static int order(String text) {
        return text.isEmpty() ? 0 : text.equals("C") ? 1 : text.equals("CW") ? 2 : text.equals("WC") ? 3 : -1;
    }

    public static int orders(int code) throws Exception {
        String[][] r = sequence(code);
        return 4 * order(r[0][0]) + order(r[1][0]);
    }
    public static int selection(int code) throws Exception {
        String[][] r = sequence(code);
        return 3 * selected(r[0][1]) + selected(r[1][1]);
    }
    private static int selected(String name) { return name.isEmpty() ? 0 : name.equals("C") ? 1 : name.equals("W") ? 2 : -1; }
    public static int lazy(int code) throws Exception {
        for (String[] call : sequence(code)) {
            if (!call[2].isEmpty() || !call[3].isEmpty() || !call[4].equals(call[1]) || !call[5].equals(call[0])) return 0;
        }
        return 1;
    }
}
