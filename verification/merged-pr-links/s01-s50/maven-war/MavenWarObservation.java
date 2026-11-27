package org.springframework.boot.maven;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.jar.JarFile;
import javax.tools.ToolProvider;
import org.junit.jupiter.api.TestTemplate;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(MavenBuildExtension.class)
class MavenWarObservation {
    @TestTemplate
    void readSingleSbom(MavenBuild build) { measure(build, false); }

    @TestTemplate
    void readWithEarlierDecoy(MavenBuild build) { measure(build, true); }

    private static void measure(MavenBuild build, boolean decoy) {
        String marker = "{\"fixture\":\"original\"}";
        String sbom = "WEB-INF/classes/META-INF/sbom/application.cdx.json";
        String other = "other/application.cdx.json";
        build.project("verified-sbom").goals("org.apache.maven.plugins:maven-war-plugin:3.5.1:war",
                "org.springframework.boot:spring-boot-maven-plugin:repackage")
                .prepare(project -> {
                    Path dir = project.toPath();
                    Path classes = Files.createDirectories(dir.resolve("target/classes"));
                    Path source = dir.resolve("Main.java");
                    Files.writeString(source, "package fixture; public class Main { public static void main(String[] args) {} }");
                    if (ToolProvider.getSystemJavaCompiler().run(null,null,null,"-proc:none","-d",classes.toString(),source.toString()) != 0)
                        throw new IllegalStateException("fixture did not compile");
                    Path payload = classes.resolve("META-INF/sbom/application.cdx.json");
                    Files.createDirectories(payload.getParent());
                    Files.writeString(payload,marker);
                    Path web = Files.createDirectories(dir.resolve("src/main/webapp"));
                    if (decoy) {
                        Files.createDirectories(web.resolve("other"));
                        Files.writeString(web.resolve(other),"{\"fixture\":\"other\"}");
                    }
                }).execute(project -> {
                    Path target = project.toPath().resolve("target/fixture-1.war");
                    try (JarFile archive = new JarFile(target.toFile())) {
                        var attributes = archive.getManifest().getMainAttributes();
                        String format = attributes.getValue("Sbom-Format");
                        String location = attributes.getValue("Sbom-Location");
                        String selected = location == null ? "absent" :
                                new String(archive.getInputStream(archive.getJarEntry(location)).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
                        if (!marker.equals(new String(archive.getInputStream(archive.getJarEntry(sbom)).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)))
                            throw new IllegalStateException("missing original Maven WAR payload");
                        List<String> entries = Collections.list(archive.entries()).stream().map(e -> e.getName()).toList();
                        if (decoy && archive.getJarEntry(other) == null) throw new IllegalStateException("missing second WAR payload");
                        String order = decoy ? Boolean.toString(entries.indexOf(other) < entries.indexOf(sbom)) : "single";
                        Path out = Path.of(System.getenv("BOOT_S48_RECEIPTS"),UUID.randomUUID() + ".txt");
                        Files.write(out,List.of(decoy ? "challenge" : "intent",String.valueOf(format),String.valueOf(location),selected,order));
                    }
                });
    }
}
