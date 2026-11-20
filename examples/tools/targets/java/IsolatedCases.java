import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Path;

/** Give every member of an exhaustive integer interval fresh application classes. */
public final class IsolatedCases {
    public static void main(String[] args) throws Exception {
        int low = Integer.parseInt(args[0]), high = Integer.parseInt(args[1]);
        URL[] paths = new URL[args.length - 2];
        for (int i = 0; i < paths.length; i++) paths[i] = Path.of(args[i + 2]).toUri().toURL();
        Thread thread = Thread.currentThread();
        ClassLoader previous = thread.getContextClassLoader();
        for (long k = low; k <= high; k++) {
            System.out.println("case " + k);
            try (URLClassLoader loader = new URLClassLoader(paths, ClassLoader.getPlatformClassLoader())) {
                thread.setContextClassLoader(loader);
                var main = Class.forName("CandidateReplay", true, loader).getDeclaredMethod("main", String[].class);
                main.setAccessible(true);
                main.invoke(null, (Object) new String[]{Long.toString(k)});
            } finally {
                thread.setContextClassLoader(previous);
            }
        }
    }
}
