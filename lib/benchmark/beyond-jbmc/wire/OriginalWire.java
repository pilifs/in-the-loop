package witness;

import java.lang.reflect.InvocationTargetException;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;

/** Each side resolves the same thin caller against its own unmodified release. */
public final class OriginalWire {
    private static final Class<?>[] sides = new Class<?>[2];

    public static void open(String callers, String oldJar, String newJar) throws Exception {
        String[] jars = {oldJar, newJar};
        for (int i = 0; i < 2; ++i) {
            URL[] urls = {Path.of(callers).toUri().toURL(), Path.of(jars[i]).toUri().toURL()};
            sides[i] = Class.forName("WireAPI", true, new URLClassLoader(urls, ClassLoader.getPlatformClassLoader()));
        }
    }

    public static Number read(int side, String name, byte[] bytes, int offset) throws Exception {
        try {
            return (Number)sides[side].getMethod(name, byte[].class, int.class).invoke(null, bytes, offset);
        } catch (InvocationTargetException e) {
            throw target(e);
        }
    }

    public static Number write(int side, String name, byte[] bytes, int offset, int value) throws Exception {
        try {
            return (Number)sides[side].getMethod(name, byte[].class, int.class, int.class).invoke(null, bytes, offset, value);
        } catch (InvocationTargetException e) {
            throw target(e);
        }
    }

    private static Exception target(InvocationTargetException e) throws Exception {
        Throwable t = e.getCause();
        if (t instanceof Exception) return (Exception)t;
        if (t instanceof Error) throw (Error)t;
        return new IllegalStateException(t);
    }
}
