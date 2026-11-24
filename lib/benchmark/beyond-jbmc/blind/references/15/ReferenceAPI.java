import java.net.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.jvnet.hudson.annotation_indexer.Index;
public final class ReferenceAPI {
    static long names(int n,boolean empty) throws java.io.IOException {
        Path dir=Files.createTempDirectory(Paths.get("."),"index-"),meta=dir.resolve("META-INF"),legacy=meta.resolve("annotations"),
             services=meta.resolve("services"),modern=services.resolve("annotations");
        Path a=legacy.resolve("java.lang.Deprecated"),b=modern.resolve("java.lang.Deprecated");
        try {
            Files.createDirectories(legacy);Files.createDirectories(modern);
            Files.write(a,"p.A\np.B\n".getBytes(StandardCharsets.UTF_8));
            if(n==1)Files.write(b,"p.B\np.C\n".getBytes(StandardCharsets.UTF_8));
            try(URLClassLoader cl=new URLClassLoader(new URL[]{dir.toUri().toURL()},ClassLoader.getPlatformClassLoader())) {
                Set<String> result=Index.listClassNames(empty?Override.class:Deprecated.class,cl);
                Set<String> expected=new HashSet<>();
                if(!empty){expected.add("p.A");expected.add("p.B");if(n==1)expected.add("p.C");}
                return result.equals(expected)?1:0;
            }
        } finally {for(Path file:new Path[]{b,a,modern,services,legacy,meta,dir})Files.deleteIfExists(file);}
    }
    public static long primary(int n) throws java.io.IOException{return names(n,false);}
    public static long control(int n) throws java.io.IOException{return names(n,true);}
}
