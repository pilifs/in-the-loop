import java.io.*;
import java.net.JarURLConnection;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.jar.JarFile;
import java.util.zip.ZipFile;
import org.gradle.launcher.GradleMain;

public class PublicCaller {
    static String hash(InputStream in) throws Exception {
        var digest=MessageDigest.getInstance("SHA-256");
        try (in) { in.transferTo(new java.security.DigestOutputStream(OutputStream.nullOutputStream(),digest)); }
        return HexFormat.of().formatHex(digest.digest());
    }
    static final String CLASS="org/gradle/api/internal/AbstractTask.class";
    static String install(Path work) throws Exception {
        var launcher=Path.of(GradleMain.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        var release=launcher.getParent().getParent();
        var zip=release.getParent().getParent().resolve("dl/gradle-D/gradle-7.6-bin.zip");
        if (!hash(Files.newInputStream(zip)).equals("7ba68c54029790ab444b39d7e293d3236b2632631fb5f2e012bb28b4ff669e4b"))
            throw new IOException("distribution digest changed");
        var origin=(JarURLConnection)PublicCaller.class.getClassLoader().getResource(CLASS).openConnection();
        var selected=Path.of(origin.getJarFileURL().toURI());
        try (var archive=new ZipFile(zip.toFile())) {
            for (var entry : Collections.list(archive.entries())) {
                if (entry.isDirectory() || !entry.getName().startsWith("gradle-7.6/lib/")) continue;
                var file=work.resolve(entry.getName());
                Files.createDirectories(file.getParent());
                if (entry.getName().equals("gradle-7.6/lib/gradle-core-7.6.jar")) Files.copy(selected,file);
                else try (var in=archive.getInputStream(entry)) { Files.copy(in,file); }
            }
        }
        try (var jar=new JarFile(selected.toFile())) { return hash(jar.getInputStream(jar.getJarEntry(CLASS))); }
    }
    static String build(Path work, Path launcher, String project, String action, String value, String classHash) throws Exception {
        var dir=work.resolve(project);
        Files.createDirectories(dir);
        Files.writeString(dir.resolve("settings.gradle"),"rootProject.name='stamp-fixture'\n");
        String script="tasks.register('stamp') { outputs.file(file('stamp.txt')); "+action+
                "('write stamp') { file('stamp.txt').text='"+value+"' } }\n";
        Files.writeString(dir.resolve("build.gradle"),script);
        var log=dir.resolve("output.log");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),
                "-Xmx192m","-XX:-UsePerfData","-Duser.home="+work,"-cp",launcher.toString(),
                "org.gradle.launcher.GradleMain","--offline","--no-daemon","--no-build-cache","--max-workers=1","--console=plain",
                "-Dorg.gradle.jvmargs=-Xmx192m","-g",work.resolve("gradle-home").toString(),
                "-I",work.resolve("provider.gradle").toString(),":stamp").directory(dir.toFile())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
        int status=proc.waitFor(); String output=Files.readString(log);
        if (status!=0 || !output.lines().anyMatch(line->line.equals("subject="+classHash)))
            throw new IOException("build or original class provider failed: "+output);
        String outcome=output.lines().filter(line->line.startsWith("> Task :stamp")).findFirst().orElseThrow();
        return outcome.substring("> Task :stamp".length()).trim()+"/"+Files.readString(dir.resolve("stamp.txt"));
    }
    static String history(String scenario, Path work, Path launcher, String pin) throws Exception {
        Files.writeString(work.resolve("provider.gradle"),"def c=org.gradle.api.internal.AbstractTask\n"
                +"def bytes=c.getResourceAsStream('AbstractTask.class').withCloseable { it.bytes }\n"
                +"println 'subject='+java.security.MessageDigest.getInstance('SHA-256').digest(bytes).encodeHex()\n");
        boolean first=scenario.equals("clean");
        String action=first ? "doFirst" : "doLast";
        String a=build(work,launcher,"incremental",action,"A",pin);
        String b=build(work,launcher,"incremental",action,scenario.equals("unchanged") ? "A" : "B",pin);
        return a+" -> "+b+(first ? " clean="+build(work,launcher,"clean",action,"B",pin) : "");
    }
    public static String observe(String[] args) throws Exception {
        Path work=Path.of("").toAbsolutePath();
        String pin=install(work);
        return history(args[0],work,work.resolve("gradle-7.6/lib/gradle-launcher-7.6.jar"),pin);
    }
}
