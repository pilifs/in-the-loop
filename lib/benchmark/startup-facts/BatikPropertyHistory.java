import java.lang.reflect.Method;
import java.net.*;
import java.nio.file.*;
import java.util.*;

/** Exercise the public lazy getter in a retained or fresh original loader. */
public class BatikPropertyHistory {
    private static Method getter;
    private static Class<?> original(URLClassLoader loader) throws Exception {
        return Class.forName("org.apache.batik.util.XMLResourceDescriptor",true,loader);
    }
    public static String sample() throws Exception { return (String)getter.invoke(null); }
    public static void main(String[] args) throws Exception {
        String mode=args[0];
        URL[] urls=Arrays.stream(args).skip(2).map(s->{
            try { return Path.of(s).toUri().toURL(); } catch(Exception e) { throw new IllegalArgumentException(e); }
        }).toArray(URL[]::new);
        try (URLClassLoader first=new URLClassLoader(urls,ClassLoader.getPlatformClassLoader())) {
            Class<?> type=original(first);
            getter=type.getMethod("getCSSParserClassName");
            if (mode.equals("setter")) type.getMethod("setCSSParserClassName",String.class).invoke(null,"fixture.ExplicitParser");
            if (mode.equals("warm") || mode.equals("fresh")) {
                System.out.println("primed="+getter.invoke(null));
                if (mode.equals("fresh")) first.close();
                // Only the evaluator's disposable copy at the selected logical path is replaced.
                Files.move(Path.of(args[1]),Path.of(args[2]),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            }
            if (mode.equals("fresh")) {
                try (URLClassLoader next=new URLClassLoader(urls,ClassLoader.getPlatformClassLoader())) {
                    getter=original(next).getMethod("getCSSParserClassName");
                    System.out.println("value="+sample());
                }
            } else System.out.println("value="+sample());
        }
    }
}
