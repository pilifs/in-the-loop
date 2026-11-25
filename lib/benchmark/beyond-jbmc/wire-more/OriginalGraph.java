package witness;

import java.io.File;
import java.lang.reflect.InvocationTargetException;
import java.net.URL;
import java.net.URLClassLoader;

public final class OriginalGraph {
    private static final ClassLoader[] sides = {loader("WIRE_ORIGINAL_BEFORE"), loader("WIRE_ORIGINAL_AFTER")};
    private static ClassLoader loader(String variable) {
        try {
            String[] files = System.getenv(variable).split(File.pathSeparator);
            URL[] urls = new URL[files.length];
            for (int i = 0; i < files.length; ++i) urls[i] = new File(files[i]).toURI().toURL();
            return new URLClassLoader(urls, ClassLoader.getPlatformClassLoader());
        } catch (Exception e) { throw new IllegalStateException(e); }
    }
    public static Object call(int side, String owner, String method, Class<?>[] types, Object... args) {
        Thread thread = Thread.currentThread();
        ClassLoader original = thread.getContextClassLoader();
        try {
            thread.setContextClassLoader(sides[side]);
            return Class.forName(owner, true, sides[side]).getMethod(method, types).invoke(null, args);
        } catch (InvocationTargetException e) {
            throw OriginalGraph.<RuntimeException>rethrow(e.getCause());
        } catch (ReflectiveOperationException e) { throw new IllegalStateException(e); }
        finally { thread.setContextClassLoader(original); }
    }
    @SuppressWarnings("unchecked")
    private static <E extends Throwable> RuntimeException rethrow(Throwable t) throws E { throw (E)t; }
}
