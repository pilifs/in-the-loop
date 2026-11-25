import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.jar.*;
import javax.tools.ToolProvider;
import org.apache.maven.cli.MavenCli;
import org.apache.maven.plugins.shade.resource.ServicesResourceTransformer;

public class PublicCaller {
    static final String PLUGIN = "org.apache.maven.plugins:maven-shade-plugin:3.3.1-SNAPSHOT";
    static Path source(Class<?> c) throws Exception {
        return Path.of(c.getProtectionDomain().getCodeSource().getLocation().toURI());
    }
    static void entry(JarOutputStream out,String name,byte[] bytes) throws IOException {
        var e=new JarEntry(name); e.setTime(0); out.putNextEntry(e); out.write(bytes); out.closeEntry();
    }
    static Path buildFixture(String id, String pkg, String impl, boolean putInterface, Path repo) throws Exception {
        Path src=Path.of(id,"src",pkg.replace('.','/')), classes=Path.of(id,"classes");
        Files.createDirectories(src); Files.createDirectories(classes);
        var service=Files.writeString(src.resolve("Svc.java"),"package "+pkg+"; public interface Svc {}");
        var provider=Files.writeString(src.resolve(impl+".java"),
                "package "+pkg+"; public class "+impl+" implements Svc {public "+impl+"() {}}");
        if (ToolProvider.getSystemJavaCompiler().run(null,null,null,"--release","8","-proc:none","-d",classes.toString(),
                service.toString(),provider.toString()) != 0) throw new IOException("fixture compilation");
        var dest=repo.resolve("fixture/"+id+"/1"); Files.createDirectories(dest);
        var jar=dest.resolve(id+"-1.jar");
        try (var out=new JarOutputStream(Files.newOutputStream(jar))) {
            String path=pkg.replace('.','/')+"/";
            for (var cls : putInterface ? List.of("Svc",impl) : List.of(impl))
                entry(out,path+cls+".class",Files.readAllBytes(classes.resolve(path+cls+".class")));
            entry(out,"META-INF/services/"+pkg+".Svc",(pkg+"."+impl+"\n").getBytes(StandardCharsets.UTF_8));
        }
        Files.writeString(dest.resolve(id+"-1.pom"),pom(id,"")); return jar;
    }
    static String pom(String artifact,String extra) {
        return "<project><modelVersion>4.0.0</modelVersion><groupId>fixture</groupId><artifactId>"+artifact
                +"</artifactId><version>1</version>"+extra+"</project>";
    }
    static String shade(Path base,Path repo,Path maven,Path plugin,Path seed,List<String> ids) throws Exception {
        Files.createDirectories(base.resolve("target/classes"));
        Files.writeString(base.resolve("target/classes/fixture.txt"),"application");
        var deps=new StringBuilder();
        for (String id : ids) deps.append("<dependency><groupId>fixture</groupId><artifactId>"+id
                +"</artifactId><version>1</version></dependency>");
        String config="<dependencies>"+deps+"</dependencies><build><plugins><plugin>"
                +"<groupId>org.apache.maven.plugins</groupId><artifactId>maven-shade-plugin</artifactId><version>3.3.1-SNAPSHOT</version>"
                +"<configuration><createDependencyReducedPom>false</createDependencyReducedPom><relocations><relocation>"
                +"<pattern>org.foo</pattern><shadedPattern>borg.foo</shadedPattern></relocation></relocations><transformers>"
                +"<transformer implementation=\"org.apache.maven.plugins.shade.resource.ServicesResourceTransformer\"/>"
                +"</transformers></configuration></plugin></plugins></build>";
        Files.writeString(base.resolve("pom.xml"),pom("application",config));
        var opts=List.of(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-Xmx160m","-XX:-UsePerfData",
                "-Xlog:class+load=info:file=loaded.log","-Dmaven.home="+maven,"-Dclassworlds.conf="+maven.resolve("bin/m2.conf"),
                "-Dmaven.multiModuleProjectDirectory="+base,"-Duser.home="+base,"-cp",maven.resolve("boot/*").toString(),
                "org.codehaus.plexus.classworlds.launcher.Launcher","-B","-o","-Dmaven.repo.local="+repo,
                "-Dmaven.repo.local.tail="+seed,"org.apache.maven.plugins:maven-jar-plugin:3.3.0:jar",PLUGIN+":shade");
        var log=base.resolve("build.log");
        var process=new ProcessBuilder(opts).directory(base.toFile()).redirectErrorStream(true).redirectOutput(log.toFile()).start();
        int status=process.waitFor();
        var loaded=Files.readString(base.resolve("loaded.log"));
        String subject=ServicesResourceTransformer.class.getName()+" source: "+plugin.toUri().toURL().toString();
        if (!loaded.contains(subject)) {
            String last=Files.readString(log);
            throw new IllegalStateException("goal did not load the registered transformer: "+last.substring(Math.max(0,last.length()-2500)));
        }
        if (status!=0) {
            if (Files.readString(log).contains("duplicate entry: META-INF/services/borg.foo.Svc")) return "duplicate descriptor";
            throw new IOException("unexpected Maven failure: "+Files.readString(log));
        }
        var file=base.resolve("target/application-1.jar");
        var paths=new ArrayList<String>(); var lines=new ArrayList<String>();
        try (var jar=new JarFile(file.toFile())) {
            for (var item : Collections.list(jar.entries())) if (!item.isDirectory() && item.getName().startsWith("META-INF/services/")) {
                paths.add(item.getName());
                try (var in=jar.getInputStream(item)) { lines.addAll(new String(in.readAllBytes(),StandardCharsets.UTF_8).lines().toList()); }
            }
        }
        paths.sort(null); lines.sort(null);
        var providers=new ArrayList<String>();
        try (var loader=new URLClassLoader(new URL[]{file.toUri().toURL()}, ClassLoader.getPlatformClassLoader())) {
            var iface=loader.loadClass("borg.foo.Svc");
            for (var p : ServiceLoader.load(iface,loader)) providers.add(p.getClass().getName()+"/"
                    +(iface.isInstance(p) && iface.getClassLoader()==loader && p.getClass().getClassLoader()==loader));
        }
        providers.sort(null);
        return paths+" "+lines+" "+providers;
    }
    public static String observe(String[] args) throws Exception {
        Path repo=Path.of("repo").toAbsolutePath(), original=source(ServicesResourceTransformer.class);
        Path maven=source(MavenCli.class).getParent().getParent();
        Path seed=original.getParent().getParent().resolve("m2");
        var coord=repo.resolve("org/apache/maven/plugins/maven-shade-plugin/3.3.1-SNAPSHOT");
        Files.createDirectories(coord);
        Path plugin=Files.copy(original,coord.resolve("maven-shade-plugin-3.3.1-SNAPSHOT.jar"));
        try (var jar=new JarFile(original.toFile()); var in=jar.getInputStream(jar.getJarEntry(
                "META-INF/maven/org.apache.maven.plugins/maven-shade-plugin/pom.xml"))) {
            Files.copy(in,coord.resolve("maven-shade-plugin-3.3.1-SNAPSHOT.pom"));
        }
        buildFixture("a","org.foo","First",true,repo); buildFixture("b","borg.foo","Second",false,repo);
        boolean control=args[0].equals("single");
        String first=shade(Path.of("first").toAbsolutePath(),repo,maven,plugin,seed, control ? List.of("a") : List.of("a","b"));
        if (!args[0].equals("reverse")) return first;
        return first+" | "+shade(Path.of("second").toAbsolutePath(),repo,maven,plugin,seed,List.of("b","a"));
    }
}
